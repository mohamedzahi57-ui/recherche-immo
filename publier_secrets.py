"""Copie les clés du fichier .env dans les "secrets" du dépôt GitHub (sans les afficher).

Utilisé par la version en ligne (.github/workflows/mise-a-jour.yml).
Lancement : publier_secrets.bat  (il faut être connecté avec « gh auth login »)
À relancer après avoir ajouté ou changé une clé dans .env (ex. MOBILITEIT_API_KEY).
"""
import os
import shutil
import subprocess
import sys

from dotenv import dotenv_values

OBLIGATOIRES = ["IMAP_USER", "IMAP_PASSWORD", "ORS_API_KEY", "SITE_PASSWORD"]
FACULTATIFS = ["MOBILITEIT_API_KEY"]
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
DOSSIER = os.path.dirname(os.path.abspath(__file__))

valeurs = dotenv_values(os.path.join(DOSSIER, ".env"))
manquants = [k for k in OBLIGATOIRES if not valeurs.get(k)]
if manquants:
    sys.exit(f"Valeurs manquantes dans .env : {', '.join(manquants)}")

login = subprocess.run([GH, "api", "user", "--jq", ".login"], capture_output=True, text=True)
if login.returncode != 0:
    sys.exit("Pas connecté à GitHub : lancez d'abord « gh auth login ».")
depot = f"{login.stdout.strip()}/recherche-immo"

for nom in OBLIGATOIRES + [k for k in FACULTATIFS if valeurs.get(k)]:
    subprocess.run([GH, "secret", "set", nom, "--repo", depot],
                   input=valeurs[nom].encode("utf-8"), check=True, cwd=DOSSIER)
    print(f"Secret {nom} enregistré sur GitHub.")
print("\nTerminé. La prochaine mise à jour en ligne utilisera ces clés.")
