"""Chef d'orchestre : lit les e-mails, extrait les annonces, supprime les doublons,
puis calcule pour chaque bien : position, trajets, frais, critères et score."""
import os
import shutil
import threading

from . import boite_mail, extraction, frais, geo, parametres, quartiers, score
from .db import connecter, journaliser, maintenant

CHAMPS_ANNONCE = ["titre", "prix", "surface", "commune", "code_postal", "pays", "type_bien", "etage",
                  "chambres", "garage", "parking", "terrasse", "neuf", "travaux", "plain_pied", "prefabrique",
                  "rez_de_chaussee"]

_verrou_import = threading.Lock()


# ---------------------------------------------------------------- doublons
def chercher_doublon(conn, a):
    """Le même bien a-t-il déjà été vu (sur un autre site, ou une autre alerte) ?
    Règle : même commune, prix à ±2 %, surface à ±3 m², même nombre de chambres (si connus)."""
    if not (a.get("commune") and a.get("prix")):
        return None
    candidats = conn.execute(
        "SELECT * FROM biens WHERE lower(commune) = lower(?) AND prix BETWEEN ? AND ?",
        (a["commune"], a["prix"] * 0.98, a["prix"] * 1.02)).fetchall()
    for c in candidats:
        if a.get("surface") and c["surface"] and abs(a["surface"] - c["surface"]) > 3:
            continue
        if a.get("chambres") is not None and c["chambres"] is not None and a["chambres"] != c["chambres"]:
            continue
        if a.get("type_bien") and c["type_bien"] and a["type_bien"] != c["type_bien"]:
            continue
        return c["id"]
    return None


def enregistrer_annonce(conn, a, message, demo=False):
    """Ajoute l'annonce. Retourne 'nouveau', 'doublon' ou 'deja_vu'."""
    if conn.execute("SELECT 1 FROM annonces WHERE source = ? AND id_externe = ?",
                    (a["source"], a["id_externe"])).fetchone():
        return "deja_vu"

    bien_id = chercher_doublon(conn, a)
    resultat = "doublon" if bien_id else "nouveau"
    if bien_id:
        # On complète les informations manquantes du bien existant (sans écraser)
        bien = conn.execute("SELECT * FROM biens WHERE id = ?", (bien_id,)).fetchone()
        maj = {k: a[k] for k in CHAMPS_ANNONCE if a.get(k) is not None and bien[k] is None}
        if bien["statut"] == "retiré":  # de nouveau en ligne : on le remet dans la liste
            conn.execute("UPDATE biens SET statut = 'nouveau', date_retrait = NULL WHERE id = ?", (bien_id,))
        if maj:
            conn.execute(f"UPDATE biens SET {', '.join(k + ' = ?' for k in maj)}, date_maj = ? WHERE id = ?",
                         (*maj.values(), maintenant(), bien_id))
    else:
        valeurs = {k: a.get(k) for k in CHAMPS_ANNONCE}
        valeurs.update(description=a.get("texte", "")[:2000], demo=1 if demo else 0,
                       date_ajout=maintenant(), date_maj=maintenant())
        cur = conn.execute(f"INSERT INTO biens({', '.join(valeurs)}) VALUES ({', '.join('?' * len(valeurs))})",
                           tuple(valeurs.values()))
        bien_id = cur.lastrowid

    conn.execute(
        "INSERT INTO annonces(bien_id, source, url, id_externe, email_id, texte_brut, date_reception) "
        "VALUES (?,?,?,?,?,?,?)",
        (bien_id, a["source"], a["url"], a["id_externe"], message["id"], a.get("texte", "")[:4000],
         message.get("date")))
    conn.commit()
    return resultat


# ---------------------------------------------------------------- enrichissement
def assurer_coordonnees_travail(conn, p, forcer=False):
    """Géolocalise l'adresse du travail une première fois (ou sur demande)."""
    deja = conn.execute("SELECT valeur FROM parametres WHERE cle = 'travail_lat'").fetchone()
    if deja and not forcer:
        return p
    lat, lon, _ = geo.geolocaliser(conn, p["travail_adresse"])
    if lat:
        parametres.ecrire(conn, {"travail_lat": lat, "travail_lon": lon})
        journaliser(conn, f"Coordonnées du travail : {lat:.5f}, {lon:.5f}")
        return parametres.lire(conn)
    journaliser(conn, "Impossible de géolocaliser l'adresse du travail (valeurs par défaut gardées).", "alerte")
    return p


def enrichir_bien(conn, bien_id, p, avec_reseau=True):
    """Calcule tout ce qui dérive des données du bien et l'enregistre."""
    b = dict(conn.execute("SELECT * FROM biens WHERE id = ?", (bien_id,)).fetchone())

    if avec_reseau and b["lat"] is None and b["commune"]:
        requete = ", ".join(x for x in (b["code_postal"], b["commune"], geo.NOMS_PAYS.get(b["pays"] or "", ""))
                            if x)
        lat, lon, pays = geo.geolocaliser(conn, requete)
        if lat:
            b["lat"], b["lon"] = lat, lon
            if not b["pays"] and pays:
                b["pays"] = pays

    if b["lat"] is not None:
        b["distance_frontiere_km"] = geo.distance_frontiere_km(b["lat"], b["lon"])
        if not b["pays"] and b["distance_frontiere_km"] == 0:
            b["pays"] = "LU"
        if avec_reseau:
            b["trajet_voiture_min"], b["trajet_voiture_source"] = geo.trajet_voiture(conn, b["lat"], b["lon"], p)
            if b["trajet_tc_source"] != "manuel":
                tc, source = geo.trajet_transports(conn, b["lat"], b["lon"], p)
                b["trajet_tc_min"], b["trajet_tc_source"] = tc, source

    b["prix_m2"] = round(b["prix"] / b["surface"]) if b["prix"] and b["surface"] else None
    b["quartier"] = None
    if quartiers.est_luxembourg_ville(b["commune"]):
        textes = [r[0] for r in conn.execute("SELECT texte_brut FROM annonces WHERE bien_id = ?", (bien_id,))]
        b["quartier"] = quartiers.trouver(*textes, b["titre"], b["description"])
    f = frais.calculer_frais(b["prix"], b["pays"], b["neuf"], p)
    b["frais_total"] = f["frais_total"] if f else None
    b["cout_total"] = f["cout_total"] if f else None
    b["hors_criteres"] = " | ".join(score.verifier_criteres(b, p))
    b["score"], _ = score.calculer_score(b, p)

    champs = ["lat", "lon", "pays", "distance_frontiere_km", "trajet_voiture_min", "trajet_voiture_source",
              "trajet_tc_min", "trajet_tc_source", "prix_m2", "frais_total", "cout_total", "hors_criteres",
              "score", "quartier"]
    conn.execute(f"UPDATE biens SET {', '.join(c + ' = ?' for c in champs)} WHERE id = ?",
                 (*[b[c] for c in champs], bien_id))
    conn.commit()


def recalculer_tout(conn, avec_reseau=False):
    """Recalcule frais/critères/score de tous les biens (après un changement de paramètres)."""
    p = parametres.lire(conn)
    for row in conn.execute("SELECT id FROM biens").fetchall():
        enrichir_bien(conn, row["id"], p, avec_reseau=avec_reseau)


# ---------------------------------------------------------------- import principal
MOT_CLE_AJOUT = "#immo"


def est_ajout_par_email(m):
    """E-mail que vous vous envoyez à vous-même avec « #immo » dans l'objet
    (ex. depuis le téléphone : Partager l'annonce > Gmail). Seule votre propre adresse est acceptée."""
    moi = (os.getenv("IMAP_USER") or "").strip().lower()
    return bool(moi) and MOT_CLE_AJOUT in (m.get("subject") or "").lower() \
        and moi in (m.get("from") or "").lower()


def ajouter_manuellement(conn, texte, url, p, origine="formulaire"):
    """Ajoute un bien à partir du texte et/ou du lien collés. Retourne (résultat, id du bien)."""
    a = extraction.annonce_manuelle(texte, url)
    message = {"id": f"{origine}:{a['source']}:{a['id_externe']}", "date": maintenant()[:16]}
    res = enregistrer_annonce(conn, a, message)
    row = conn.execute("SELECT bien_id FROM annonces WHERE source = ? AND id_externe = ?",
                       (a["source"], a["id_externe"])).fetchone()
    bien_id = row["bien_id"] if row else None
    if bien_id and res != "deja_vu":
        enrichir_bien(conn, bien_id, p)
    return res, bien_id


def traiter_messages(conn, messages, p, demo=False):
    stats = {"emails": 0, "nouveaux": 0, "doublons": 0, "ignores": 0}
    for m in messages:
        if conn.execute("SELECT 1 FROM emails_traites WHERE message_id = ?", (m["id"],)).fetchone():
            continue
        if est_ajout_par_email(m):
            texte = m.get("text") or extraction.BeautifulSoup(m.get("html") or "", "html.parser").get_text(" ")
            res, _ = ajouter_manuellement(conn, texte, "", p, origine="email")
            stats["nouveaux" if res == "nouveau" else "doublons"] += res != "deja_vu"
            conn.execute("INSERT OR IGNORE INTO emails_traites VALUES (?,?,?,?,?,?,?)",
                         (m["id"], m["subject"], m["from"], m["date"], 1, m["origine"], maintenant()))
            conn.commit()
            stats["emails"] += 1
            continue
        if m["origine"] != "fichier" and not boite_mail.expediteur_autorise(m["from"], p["expediteurs_alertes"]):
            stats["ignores"] += 1
            continue
        annonces = extraction.extraire_annonces(m)
        nb = 0
        for a in annonces:
            res = enregistrer_annonce(conn, a, m, demo=demo)
            if res == "nouveau":
                stats["nouveaux"] += 1
                nb += 1
            elif res == "doublon":
                stats["doublons"] += 1
        conn.execute("INSERT OR IGNORE INTO emails_traites VALUES (?,?,?,?,?,?,?)",
                     (m["id"], m["subject"], m["from"], m["date"], len(annonces), m["origine"], maintenant()))
        conn.commit()
        stats["emails"] += 1
        if m.get("chemin") and not demo:  # fichier .eml déposé : on le range pour ne pas le relire
            dossier = os.path.join(os.path.dirname(m["chemin"]), "deja_importes")
            os.makedirs(dossier, exist_ok=True)
            shutil.move(m["chemin"], os.path.join(dossier, os.path.basename(m["chemin"])))
    return stats


def _relire_alertes_immotop(conn):
    """Une seule fois : les alertes Immotop lues avant que l'appli sache les décoder
    (0 annonce trouvée) sont oubliées pour être relues. Retourne la date de la plus ancienne."""
    if conn.execute("SELECT 1 FROM parametres WHERE cle = '_relu_immotop'").fetchone():
        return None
    filtre = ("FROM emails_traites WHERE nb_annonces = 0 AND expediteur LIKE '%immotop%' "
              "AND sujet LIKE '%nouvelle%annonce%'")
    plus_ancienne = conn.execute("SELECT min(date_reception) d " + filtre).fetchone()["d"]
    conn.execute("DELETE " + filtre)
    conn.execute("INSERT OR REPLACE INTO parametres(cle, valeur) VALUES ('_relu_immotop', 'true')")
    conn.commit()
    return plus_ancienne


def corriger_communes(conn):
    """Une seule fois : relit la commune de chaque bien avec la règle « premier nom de lieu du texte »
    (avant, le nom de l'agence, ex. « Engel & Völkers LUXEMBOURG », pouvait l'emporter).
    Les communes corrigées à la main ne sont pas touchées. Les biens modifiés seront relocalisés."""
    if conn.execute("SELECT 1 FROM parametres WHERE cle = '_communes_v2'").fetchone():
        return 0
    from . import communes
    corriges = 0
    for b in conn.execute("SELECT id, commune, pays, titre, champs_modifies FROM biens").fetchall():
        if "commune" in (b["champs_modifies"] or "").split(","):
            continue
        a = conn.execute("SELECT texte_brut, url FROM annonces WHERE bien_id = ? ORDER BY id LIMIT 1",
                         (b["id"],)).fetchone()
        if not a:
            continue
        nom, pays = communes.trouver_commune(a["texte_brut"] or "")
        if not nom or nom == b["commune"] or (nom == "Luxembourg" and b["commune"]):
            continue
        titre = b["titre"] or ""
        if b["commune"] and titre.endswith(b["commune"]):
            titre = titre[: -len(b["commune"])] + nom
        conn.execute("UPDATE biens SET commune = ?, pays = ?, titre = ?, quartier = NULL, lat = NULL, lon = NULL, "
                     "trajet_voiture_min = NULL, trajet_voiture_source = NULL, date_maj = ? WHERE id = ?",
                     (nom, pays, titre, maintenant(), b["id"]))
        corriges += 1
    conn.execute("INSERT OR REPLACE INTO parametres(cle, valeur) VALUES ('_communes_v2', 'true')")
    conn.commit()
    if corriges:
        journaliser(conn, f"Communes relues : {corriges} bien(s) corrigé(s) et relocalisé(s).")
    return corriges


def completer_quartiers(conn):
    """Quartier des biens de Luxembourg-ville qui n'en ont pas encore (calcul rapide, sans réseau)."""
    for b in conn.execute("SELECT id, commune, titre, description FROM biens WHERE quartier IS NULL").fetchall():
        if quartiers.est_luxembourg_ville(b["commune"]):
            textes = [r[0] for r in conn.execute("SELECT texte_brut FROM annonces WHERE bien_id = ?", (b["id"],))]
            q = quartiers.trouver(*textes, b["titre"], b["description"])
            if q:
                conn.execute("UPDATE biens SET quartier = ? WHERE id = ?", (q, b["id"]))
    conn.commit()


def importer(demo_dossier=None):
    """Lance un import complet. Retourne un résumé texte."""
    if not _verrou_import.acquire(blocking=False):
        return "Un import est déjà en cours."
    try:
        with connecter() as conn:
            p = parametres.lire(conn)
            p = assurer_coordonnees_travail(conn, p)
            derniere = conn.execute("SELECT max(date_traitement) d FROM emails_traites "
                                    "WHERE origine != 'fichier'").fetchone()["d"]
            depuis = boite_mail.date_depart(derniere, p["import_jours_historique"])
            a_relire = _relire_alertes_immotop(conn)
            if a_relire:
                depuis = min(depuis, boite_mail.date_depart(a_relire, 0))

            messages = []
            if demo_dossier:
                messages += boite_mail.lire_dossier_local(demo_dossier)
            else:
                messages += boite_mail.lire_dossier_local()
                if boite_mail.graph_configure():
                    try:
                        messages += boite_mail.lire_graph(depuis)
                    except Exception as e:
                        journaliser(conn, f"Outlook : {e}", "erreur")
                if boite_mail.imap_configure():
                    try:
                        messages += boite_mail.lire_imap(depuis)
                    except Exception as e:
                        journaliser(conn, f"IMAP : {e}", "erreur")

            stats = traiter_messages(conn, messages, p, demo=bool(demo_dossier))
            corriger_communes(conn)

            # Enrichissement des biens incomplets (position / trajets manquants)
            a_enrichir = conn.execute(
                "SELECT id FROM biens WHERE lat IS NULL OR trajet_voiture_min IS NULL "
                "OR trajet_voiture_source = 'estimation' OR score IS NULL").fetchall()
            for row in a_enrichir:
                enrichir_bien(conn, row["id"], p)
            completer_quartiers(conn)

            resume = (f"Import terminé : {stats['emails']} e-mail(s) lu(s), {stats['nouveaux']} nouveau(x) "
                      f"bien(s), {stats['doublons']} doublon(s) regroupé(s), {stats['ignores']} e-mail(s) "
                      f"ignoré(s) (autres expéditeurs).")
            journaliser(conn, resume)
            return resume
    except Exception as e:
        with connecter() as conn:
            journaliser(conn, f"Erreur pendant l'import : {e}", "erreur")
        raise
    finally:
        _verrou_import.release()


def supprimer_demo():
    with connecter() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM biens WHERE demo = 1")]
        conn.execute("DELETE FROM annonces WHERE bien_id IN (SELECT id FROM biens WHERE demo = 1)")
        conn.execute("DELETE FROM biens WHERE demo = 1")
        conn.execute("DELETE FROM emails_traites WHERE message_id LIKE '%demo%'")
        conn.commit()
        journaliser(conn, f"{len(ids)} bien(s) de démonstration supprimé(s).")
