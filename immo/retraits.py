"""Repère les annonces retirées des sites et retire les biens correspondants de la liste.

Comment : on demande au site si la page de l'annonce existe encore (simple requête HEAD,
sans télécharger la page). atHome répond « 410 Gone » ou « 404 » quand l'annonce n'existe plus.

Limites : Immotop et SeLoger bloquent les programmes automatiques (réponse 403) ; on ne
cherche pas à contourner cette protection. Leurs annonces ne sont donc pas vérifiées.

Un bien est marqué « retiré » (statut = 'retiré') quand au moins une de ses annonces a
disparu et qu'aucune autre n'a été vue encore en ligne. Il disparaît de la liste (PC et
téléphone) mais reste dans la base : rien n'est effacé, on peut le remettre depuis la fiche.
"""
import os
import re
import time

import requests

from . import db

ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
RE_ATHOME = re.compile(r"athome\.lu/(?:[\w/-]+/)?id-(\d+)\.html")
DISPARUE = {404, 410}


def url_a_verifier(source, url):
    """Adresse à interroger pour cette annonce, ou None si le site ne se vérifie pas."""
    m = RE_ATHOME.search(url or "")
    if m:
        return f"https://www.athome.lu/id-{m.group(1)}.html"
    return None


def etat_annonce(url, session=None):
    """'en_ligne', 'retiree' ou 'inconnu' (site bloqué, panne réseau...)."""
    try:
        r = (session or requests).head(url, headers=ENTETES, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return "inconnu", None
    if r.status_code in DISPARUE:
        return "retiree", r.status_code
    if r.status_code == 200:
        return "en_ligne", 200
    return "inconnu", r.status_code


def verifier(conn, maximum=200, pause=1.0):
    """Vérifie les annonces les moins récemment contrôlées. Renvoie un petit bilan."""
    lignes = conn.execute(
        "SELECT a.id, a.bien_id, a.source, a.url FROM annonces a JOIN biens b ON b.id = a.bien_id "
        "WHERE COALESCE(a.retiree, 0) = 0 AND COALESCE(b.statut, '') != 'retiré' AND b.demo = 0 "
        "AND a.url LIKE '%athome.lu%' ORDER BY a.verifie_le IS NOT NULL, a.verifie_le LIMIT ?",
        (maximum,)).fetchall()
    bilan = {"verifiees": 0, "retirees": 0, "inconnues": 0, "biens_retires": 0}
    biens_touches = set()
    session = requests.Session()
    bloque_de_suite = 0
    for ligne in lignes:
        url = url_a_verifier(ligne["source"], ligne["url"])
        if not url:
            continue
        etat, code = etat_annonce(url, session)
        if etat == "inconnu":
            bilan["inconnues"] += 1
            bloque_de_suite += 1
            if bloque_de_suite >= 5:  # le site nous bloque ou est en panne : on arrête poliment
                db.journaliser(conn, f"Vérification des retraits interrompue (réponse {code}).", "alerte")
                break
        else:
            bloque_de_suite = 0
            bilan["verifiees"] += 1
            conn.execute("UPDATE annonces SET verifie_le = ?, retiree = ? WHERE id = ?",
                         (db.maintenant(), 1 if etat == "retiree" else 0, ligne["id"]))
            if etat == "retiree":
                bilan["retirees"] += 1
                biens_touches.add(ligne["bien_id"])
        time.sleep(pause)
    conn.commit()
    for bien_id in biens_touches:
        if retirer_si_disparu(conn, bien_id):
            bilan["biens_retires"] += 1
    conn.commit()
    if bilan["verifiees"] or bilan["inconnues"]:
        db.journaliser(conn, "Vérification des annonces retirées : {verifiees} vérifiées, {retirees} disparues, "
                             "{biens_retires} bien(s) retiré(s) de la liste, {inconnues} sans réponse.".format(**bilan))
    return bilan


def retirer_si_disparu(conn, bien_id):
    """Retire le bien si une annonce a disparu et qu'aucune n'a été vue encore en ligne."""
    annonces = conn.execute("SELECT retiree, verifie_le FROM annonces WHERE bien_id = ?", (bien_id,)).fetchall()
    disparues = [a for a in annonces if a["retiree"] == 1]
    vues_en_ligne = [a for a in annonces if a["retiree"] != 1 and a["verifie_le"]]
    if disparues and not vues_en_ligne:
        conn.execute("UPDATE biens SET statut = 'retiré', date_retrait = ? WHERE id = ?",
                     (db.maintenant()[:10], bien_id))
        return True
    return False


# ---------------------------------------------------------------- retrait signalé par vous
# Le PC et la version en ligne ont chacun leur base : un retrait fait sur le PC part donc par
# e-mail (à vous-même, objet « #retire »), que la routine en ligne lit comme les alertes.
MOT_CLE_RETRAIT = "#retire"
RE_CLE = re.compile(r"annonce\s*:\s*([^|\n]+?)\s*\|\s*(\S+)", re.I)


def est_email_retrait(m):
    moi = (os.getenv("IMAP_USER") or "").strip().lower()
    return bool(moi) and MOT_CLE_RETRAIT in (m.get("subject") or "").lower() \
        and moi in (m.get("from") or "").lower()


def corps_email_retrait(conn, bien_id):
    """Texte de l'e-mail : une ligne « annonce: source|identifiant » par annonce du bien, plus les liens."""
    lignes = ["Annonce retirée du site : ce bien sera retiré de la liste (PC et téléphone).", ""]
    for a in conn.execute("SELECT source, id_externe, url FROM annonces WHERE bien_id = ?", (bien_id,)):
        lignes.append(f"annonce: {a['source']}|{a['id_externe']}")
        if a["url"]:
            lignes.append(a["url"])
    return "\n".join(lignes)


def appliquer_email_retrait(conn, texte):
    """Retire les biens désignés dans l'e-mail (clés « annonce: » ou liens d'annonce). Renvoie leur nombre."""
    from . import extraction
    biens = set()
    for source, ident in RE_CLE.findall(texte or ""):
        r = conn.execute("SELECT bien_id FROM annonces WHERE source = ? AND id_externe = ?",
                         (source.strip(), ident.strip())).fetchone()
        if r:
            biens.add(r["bien_id"])
    for url in extraction.RE_URL.findall(texte or ""):
        source, ident = extraction.identifier_annonce(url)
        if source:
            r = conn.execute("SELECT bien_id FROM annonces WHERE source = ? AND id_externe = ?",
                             (source, ident)).fetchone()
            if r:
                biens.add(r["bien_id"])
    for bien_id in biens:
        conn.execute("UPDATE biens SET statut = 'retiré', date_retrait = COALESCE(date_retrait, ?) WHERE id = ?",
                     (db.maintenant()[:10], bien_id))
    conn.commit()
    if biens:
        db.journaliser(conn, f"Retrait signalé par e-mail : {len(biens)} bien(s) retiré(s) de la liste.")
    return len(biens)


if __name__ == "__main__":
    import sys
    db.initialiser()
    with db.connecter() as c:
        print(verifier(c, maximum=int(sys.argv[1]) if len(sys.argv) > 1 else 200))
