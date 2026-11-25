"""Fabrique la version en ligne (consultation seule) de l'application.

Résultat : le dossier site/, prêt à être publié tel quel (GitHub Pages) :
  - index.html : une seule page qui contient TOUTES les pages de l'application
    (liste, tris, fiches), compressées puis chiffrées avec le mot de passe SITE_PASSWORD.
    Sans le mot de passe, le contenu est illisible ; avec, le téléphone l'ouvre
    et le garde en mémoire pour les fois suivantes ;
  - manifest + icônes + service worker : pour l'installer comme une application.

Les pages sont produites par l'application Flask elle-même (mêmes calculs, même
présentation), avec la variable "statique" qui masque les formulaires de modification.

Lancement : python exporter_site.py   (utilise data/immo.db et le .env)
"""
import gzip
import html
import json
import os
import re
import shutil
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
os.environ.pop("APP_PASSWORD", None)  # pas d'authentification pour l'export local

import app as application  # noqa: E402
from immo import chiffrement, db  # noqa: E402

DOSSIER = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(DOSSIER, "site")
RE_LIEN = re.compile(r"""(?:href="|location\.href=')(/[^"']*)""")


def _page_a_exporter(url):
    return url == "/" or url.startswith("/?") or re.fullmatch(r"/bien/\d+", url)


def collecter_pages():
    """Parcourt l'application comme un visiteur, à partir de la liste, et garde chaque page."""
    flask_app = application.app
    flask_app.jinja_env.globals["statique"] = True
    flask_app.jinja_env.globals["mise_a_jour"] = datetime.now(ZoneInfo("Europe/Luxembourg")).strftime(
        "%d/%m/%Y à %H:%M")
    client = flask_app.test_client()
    pages, a_voir, vues = {}, deque(["/", "/?tous=1"]), set()
    while a_voir and len(pages) < 3000:
        url = a_voir.popleft()
        if url in vues:
            continue
        vues.add(url)
        rep = client.get(url)
        if rep.status_code != 200:
            continue
        texte = rep.get_data(as_text=True)
        corps = texte.split("<body>", 1)[-1].rsplit("</body>", 1)[0]
        # les lignes du tableau ouvrent la fiche par JavaScript : on passe par notre routeur
        pages[url] = re.sub(r"location\.href='([^']*)'", r"aller('\1')", corps)
        for lien in RE_LIEN.findall(texte):
            lien = html.unescape(lien)
            if _page_a_exporter(lien) and lien not in vues:
                a_voir.append(lien)
    return pages


def ecrire_site(pages, mot_de_passe):
    # on vide le dossier (sans le supprimer : il peut être ouvert ailleurs)
    os.makedirs(SORTIE, exist_ok=True)
    for nom in os.listdir(SORTIE):
        chemin = os.path.join(SORTIE, nom)
        shutil.rmtree(chemin) if os.path.isdir(chemin) else os.remove(chemin)
    os.makedirs(os.path.join(SORTIE, "icones"))
    paquet = chiffrement.chiffrer(gzip.compress(json.dumps(pages).encode("utf-8")), mot_de_passe)
    with open(os.path.join(DOSSIER, "static", "style.css"), encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(DOSSIER, "site_modele", "index.html"), encoding="utf-8") as f:
        modele = f.read()
    page = modele.replace("/*CSS*/", css).replace('"__DONNEES__"', json.dumps(paquet))
    with open(os.path.join(SORTIE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    for nom in ("manifest.webmanifest", "sw.js"):
        shutil.copy(os.path.join(DOSSIER, "site_modele", nom), SORTIE)
    for nom in os.listdir(os.path.join(DOSSIER, "static", "icones")):
        shutil.copy(os.path.join(DOSSIER, "static", "icones", nom), os.path.join(SORTIE, "icones"))
    open(os.path.join(SORTIE, ".nojekyll"), "w").close()
    return os.path.getsize(os.path.join(SORTIE, "index.html"))


if __name__ == "__main__":
    db.initialiser()
    pages = collecter_pages()
    taille = ecrire_site(pages, chiffrement.mot_de_passe())
    print(f"Site exporté : {len(pages)} pages, index.html = {taille // 1024} Ko -> {SORTIE}")
