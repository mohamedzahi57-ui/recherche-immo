"""Copie les clés du fichier .env dans les "secrets" du dépôt GitHub (sans les afficher).

Utilisé par la version en ligne (.github/workflows/mise-a-jour.yml).
Lancement : publier_secrets.bat  (il faut être connecté avec « gh auth login »)
"""
import os
import shutil
import subprocess
import sys

from dotenv import dotenv_values

SECRETS = ["IMAP_USER", "IMAP_PASSWORD", "ORS_API_KEY", "SITE_PASSWORD"]
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"

valeurs = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
manquants = [k for k in SECRETS if not valeurs.get(k)]
if manquants:
    sys.exit(f"Valeurs manquantes dans .env : {', '.join(manquants)}")
for nom in SECRETS:
    subprocess.run([GH, "secret", "set", nom], input=valeurs[nom].encode("utf-8"), check=True)
    print(f"Secret {nom} enregistré sur GitHub.")
