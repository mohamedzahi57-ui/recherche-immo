"""Démarrage silencieux de l'application (sans fenêtre noire).

Lancé automatiquement à l'ouverture de session Windows grâce au raccourci
« Recherche immo » placé dans le dossier Démarrage (voir installer_demarrage_auto.bat).
Les messages de l'application sont écrits dans data/app.log au lieu d'une fenêtre.
"""
import os
import socket
import sys

DOSSIER = os.path.dirname(os.path.abspath(__file__))
os.chdir(DOSSIER)
sys.path.insert(0, DOSSIER)
os.makedirs("data", exist_ok=True)

# Pas de fenêtre : on redirige les messages vers un fichier journal
journal = open(os.path.join("data", "app.log"), "a", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = journal

# Si l'application tourne déjà (par ex. lancée avec lancer.bat), on ne fait rien
with socket.socket() as s:
    if s.connect_ex(("127.0.0.1", int(os.getenv("PORT", "5000")))) == 0:
        print("Application déjà lancée : rien à faire.")
        sys.exit(0)

import runpy  # noqa: E402

runpy.run_path(os.path.join(DOSSIER, "app.py"), run_name="__main__")
