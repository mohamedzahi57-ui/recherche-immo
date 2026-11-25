"""Première mise en ligne de la version consultation (à lancer une seule fois).

Ce que fait ce script, dans l'ordre :
  1. crée le dépôt GitHub public « recherche-immo » (code seulement : .env, data/ et site/
     sont exclus par .gitignore) ;
  2. copie les clés de .env dans les secrets GitHub (jamais affichées, jamais dans le code) ;
  3. envoie la base actuelle, CHIFFRÉE, sur la branche « donnees » ;
  4. active GitHub Pages ;
  5. envoie le code : la première mise à jour démarre aussitôt sur GitHub.

Lancement : double-clic sur mettre_en_ligne.bat (il faut être connecté avec « gh auth login »).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from dotenv import load_dotenv

DOSSIER = os.path.dirname(os.path.abspath(__file__))
os.chdir(DOSSIER)
load_dotenv()
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
DEPOT = "recherche-immo"


def lancer(*cmd, entree=None, sortie=False, cwd=None):
    r = subprocess.run(cmd, input=entree, capture_output=True, cwd=cwd)
    if r.returncode != 0:
        print(r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))
        sys.exit(f"Échec : {' '.join(cmd[:3])}")
    return r.stdout.decode("utf-8").strip() if sortie else None


login = lancer(GH, "api", "user", "--jq", ".login", sortie=True)
ident = lancer(GH, "api", "user", "--jq", ".id", sortie=True)
complet = f"{login}/{DEPOT}"
url = f"https://github.com/{complet}.git"
print(f"Compte GitHub : {login}")

# 0. dépôt local (identité GitHub anonyme, pas votre e-mail)
if not os.path.isdir(".git"):
    lancer("git", "init", "-q", "-b", "main")
lancer("git", "config", "user.name", login)
lancer("git", "config", "user.email", f"{ident}+{login}@users.noreply.github.com")
lancer("git", "add", "-A")
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
    lancer("git", "commit", "-q", "-m", "Recherche immo : application + version en ligne chiffrée")

# 1. dépôt GitHub
existe = subprocess.run([GH, "repo", "view", complet], capture_output=True).returncode == 0
if not existe:
    lancer(GH, "repo", "create", DEPOT, "--public",
           "--description", "Recherche immobiliere personnelle - donnees chiffrees")
    print("1/5 Dépôt créé.")
if subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True).returncode != 0:
    lancer("git", "remote", "add", "origin", url)

# 2. secrets
for nom in ("IMAP_USER", "IMAP_PASSWORD", "ORS_API_KEY", "SITE_PASSWORD"):
    valeur = os.getenv(nom)
    if not valeur:
        sys.exit(f"{nom} manquant dans .env")
    lancer(GH, "secret", "set", nom, "--repo", complet, entree=valeur.encode("utf-8"))
print("2/5 Secrets enregistrés sur GitHub.")

# 3. base chiffrée sur la branche « donnees »
from immo import chiffrement  # noqa: E402

with open(os.path.join("data", "immo.db"), "rb") as f:
    paquet = json.dumps(chiffrement.chiffrer(f.read(), os.environ["SITE_PASSWORD"]))
with tempfile.TemporaryDirectory() as tmp:
    with open(os.path.join(tmp, "immo.db.chiffre"), "w") as f:
        f.write(paquet)
    lancer("git", "init", "-q", "-b", "donnees", cwd=tmp)
    lancer("git", "add", "immo.db.chiffre", cwd=tmp)
    lancer("git", "-c", f"user.name={login}", "-c", f"user.email={ident}+{login}@users.noreply.github.com",
           "commit", "-q", "-m", "Base de données (chiffrée)", cwd=tmp)
    lancer("git", "push", "-q", "-f", url, "donnees", cwd=tmp)
print("3/5 Base envoyée (chiffrée).")

# 4. GitHub Pages (publication par la tâche automatique)
if subprocess.run([GH, "api", f"repos/{complet}/pages"], capture_output=True).returncode != 0:
    lancer(GH, "api", "-X", "POST", f"repos/{complet}/pages", "-f", "build_type=workflow")
print("4/5 GitHub Pages activé.")

# 5. code : déclenche la première mise à jour
lancer("git", "push", "-q", "-u", "origin", "main")
print("5/5 Code envoyé : la première mise à jour tourne sur GitHub (3 à 5 minutes).")
print(f"\nAdresse de l'application : https://{login.lower()}.github.io/{DEPOT}/")
