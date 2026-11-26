"""Chef d'orchestre : lit les e-mails, extrait les annonces, supprime les doublons,
puis calcule pour chaque bien : position, trajets, frais, critères et score."""
import os
import shutil
import threading

from . import boite_mail, extraction, frais, geo, parametres, score
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
    f = frais.calculer_frais(b["prix"], b["pays"], b["neuf"], p)
    b["frais_total"] = f["frais_total"] if f else None
    b["cout_total"] = f["cout_total"] if f else None
    b["hors_criteres"] = " | ".join(score.verifier_criteres(b, p))
    b["score"], _ = score.calculer_score(b, p)

    champs = ["lat", "lon", "pays", "distance_frontiere_km", "trajet_voiture_min", "trajet_voiture_source",
              "trajet_tc_min", "trajet_tc_source", "prix_m2", "frais_total", "cout_total", "hors_criteres",
              "score"]
    conn.execute(f"UPDATE biens SET {', '.join(c + ' = ?' for c in champs)} WHERE id = ?",
                 (*[b[c] for c in champs], bien_id))
    conn.commit()


def recalculer_tout(conn, avec_reseau=False):
    """Recalcule frais/critères/score de tous les biens (après un changement de paramètres)."""
    p = parametres.lire(conn)
    for row in conn.execute("SELECT id FROM biens").fetchall():
        enrichir_bien(conn, row["id"], p, avec_reseau=avec_reseau)


# ---------------------------------------------------------------- import principal
def traiter_messages(conn, messages, p, demo=False):
    stats = {"emails": 0, "nouveaux": 0, "doublons": 0, "ignores": 0}
    for m in messages:
        if conn.execute("SELECT 1 FROM emails_traites WHERE message_id = ?", (m["id"],)).fetchone():
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

            # Enrichissement des biens incomplets (position / trajets manquants)
            a_enrichir = conn.execute(
                "SELECT id FROM biens WHERE lat IS NULL OR trajet_voiture_min IS NULL "
                "OR trajet_voiture_source = 'estimation' OR score IS NULL").fetchall()
            for row in a_enrichir:
                enrichir_bien(conn, row["id"], p)

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
