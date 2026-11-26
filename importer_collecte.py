"""Importe dans l'appli les annonces relevées sur les sites (fichiers data/collecte/*.json).

Chaque fichier : {"source": "...", "annonces": [{"url": "...", "texte": "..."}, ...]}
Les annonces déjà connues sont ignorées, les doublons entre sites sont regroupés.
Lancement : .venv\\Scripts\\python importer_collecte.py
"""
import glob
import json
import os

from dotenv import load_dotenv

DOSSIER = os.path.dirname(os.path.abspath(__file__))
os.chdir(DOSSIER)
load_dotenv(os.path.join(DOSSIER, ".env"))

from immo import db, importeur, parametres  # noqa: E402

db.initialiser()
stats = {"nouveau": 0, "doublon": 0, "deja_vu": 0}
with db.connecter() as conn:
    p = importeur.assurer_coordonnees_travail(conn, parametres.lire(conn))
    for chemin in sorted(glob.glob(os.path.join("data", "collecte", "*.json"))):
        donnees = json.load(open(chemin, encoding="utf-8"))
        annonces = donnees["annonces"]
        print(f"{os.path.basename(chemin)} : {len(annonces)} annonces", flush=True)
        for i, a in enumerate(annonces, 1):
            res, _ = importeur.ajouter_manuellement(conn, a.get("texte", ""), a.get("url", ""), p,
                                                    origine="collecte")
            stats[res] += 1
            if i % 50 == 0:
                print(f"  {i}/{len(annonces)} {stats}", flush=True)
    db.journaliser(conn, f"Annonces existantes relevées sur les sites : {stats['nouveau']} nouveau(x) bien(s), "
                         f"{stats['doublon']} doublon(s) regroupé(s), {stats['deja_vu']} déjà connue(s).")
print("Terminé :", stats)
