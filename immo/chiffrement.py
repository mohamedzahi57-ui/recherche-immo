"""Chiffrement par mot de passe (AES-256-GCM, clé dérivée par PBKDF2-SHA256).

Sert à deux choses pour la version en ligne :
  - le site publié (index.html) : son contenu est chiffré, le navigateur le déchiffre
    avec le mot de passe (WebCrypto, mêmes paramètres) ;
  - la base de données gardée sur GitHub (data/immo.db.chiffre).

Le mot de passe vient de la variable d'environnement SITE_PASSWORD (.env ou secret GitHub).

Ligne de commande :
  python -m immo.chiffrement chiffrer   data/immo.db         data/immo.db.chiffre
  python -m immo.chiffrement dechiffrer data/immo.db.chiffre data/immo.db
"""
import base64
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 310_000


def _b64(octets):
    return base64.b64encode(octets).decode("ascii")


def _cle(mot_de_passe, sel, iterations=ITERATIONS):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sel, iterations=iterations)
    return kdf.derive(mot_de_passe.encode("utf-8"))


def chiffrer(donnees, mot_de_passe):
    """octets -> dictionnaire JSON-isable {iter, sel, iv, ct} (ct = texte chiffré + étiquette GCM)."""
    sel, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_cle(mot_de_passe, sel)).encrypt(iv, donnees, None)
    return {"v": 1, "iter": ITERATIONS, "sel": _b64(sel), "iv": _b64(iv), "ct": _b64(ct)}


def dechiffrer(paquet, mot_de_passe):
    sel, iv, ct = (base64.b64decode(paquet[k]) for k in ("sel", "iv", "ct"))
    return AESGCM(_cle(mot_de_passe, sel, paquet["iter"])).decrypt(iv, ct, None)


def mot_de_passe():
    mdp = os.getenv("SITE_PASSWORD")
    if not mdp:
        sys.exit("SITE_PASSWORD manquant (fichier .env ou secret GitHub).")
    return mdp


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    action, source, cible = sys.argv[1:4]
    with open(source, "rb") as f:
        contenu = f.read()
    if action == "chiffrer":
        sortie = json.dumps(chiffrer(contenu, mot_de_passe())).encode("ascii")
    elif action == "dechiffrer":
        sortie = dechiffrer(json.loads(contenu), mot_de_passe())
    else:
        sys.exit("action inconnue : chiffrer ou dechiffrer")
    with open(cible, "wb") as f:
        f.write(sortie)
    print(f"{action} : {source} -> {cible}")
