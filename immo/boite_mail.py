"""Récupération des e-mails d'alerte.

Trois façons de lire les e-mails (on peut en utiliser plusieurs) :
  1. API Microsoft Graph (Outlook / Hotmail) — recommandé pour mz57@hotmail.fr.
     Microsoft n'accepte plus le simple mot de passe en IMAP pour Outlook.com :
     il faut une "autorisation" (OAuth). On l'obtient une seule fois en tapant un
     code sur https://microsoft.com/devicelogin depuis la page Import.
  2. IMAP classique (ex. Gmail avec mot de passe d'application) si vous préférez
     transférer automatiquement les alertes vers une autre boîte.
  3. Dossier local data/emails_a_importer : fichiers .eml déposés à la main
     (aussi utilisé pour le mode démo).

Chaque e-mail est converti en dictionnaire :
  {'id', 'subject', 'from', 'date', 'html', 'text', 'origine'}
"""
import email
import glob
import imaplib
import os
import threading
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

import requests

from .db import DOSSIER_DATA

DOSSIER_EML = os.path.join(DOSSIER_DATA, "emails_a_importer")
CACHE_MSAL = os.path.join(DOSSIER_DATA, "jeton_microsoft.bin")
SCOPES_GRAPH = ["Mail.Read"]


# ---------------------------------------------------------------- utilitaires
def _decoder_entete(valeur):
    try:
        return str(make_header(decode_header(valeur or "")))
    except Exception:
        return valeur or ""


def depuis_rfc822(brut, origine):
    """Transforme un e-mail brut (format standard .eml) en dictionnaire."""
    msg = email.message_from_bytes(brut)
    html, text = "", ""
    for partie in msg.walk():
        type_contenu = partie.get_content_type()
        if partie.get_content_maintype() == "multipart" or partie.get_filename():
            continue
        try:
            contenu = partie.get_payload(decode=True)
            if contenu is None:
                continue
            charset = partie.get_content_charset() or "utf-8"
            contenu = contenu.decode(charset, errors="replace")
        except Exception:
            continue
        if type_contenu == "text/html":
            html += contenu
        elif type_contenu == "text/plain":
            text += contenu
    try:
        date = parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        date = ""
    return {
        "id": msg.get("Message-ID") or f"{origine}:{_decoder_entete(msg.get('Subject'))}:{date}",
        "subject": _decoder_entete(msg.get("Subject")),
        "from": _decoder_entete(msg.get("From")),
        "date": date,
        "html": html,
        "text": text,
        "origine": origine,
    }


def expediteur_autorise(expediteur, domaines):
    expediteur = (expediteur or "").lower()
    return any(d.strip().lower() in expediteur for d in domaines.split(",") if d.strip())


# ---------------------------------------------------------------- 3. dossier local
def lire_dossier_local(dossier=DOSSIER_EML):
    """Lit les fichiers .eml d'un dossier. Les fichiers lus sont déplacés dans 'deja_importes'."""
    os.makedirs(dossier, exist_ok=True)
    messages = []
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.eml"))):
        with open(chemin, "rb") as f:
            m = depuis_rfc822(f.read(), "fichier")
        m["chemin"] = chemin
        messages.append(m)
    return messages


# ---------------------------------------------------------------- 2. IMAP
def imap_configure():
    return all(os.getenv(k) for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD"))


def lire_imap(depuis):
    """Lit les e-mails reçus depuis la date donnée dans le dossier IMAP configuré."""
    hote = os.getenv("IMAP_HOST")
    boite = imaplib.IMAP4_SSL(hote)
    try:
        boite.login(os.getenv("IMAP_USER"), os.getenv("IMAP_PASSWORD"))
        boite.select(os.getenv("IMAP_FOLDER") or "INBOX", readonly=True)
        critere = depuis.strftime("%d-%b-%Y")
        _, data = boite.search(None, f'(SINCE "{critere}")')
        messages = []
        for num in data[0].split():
            _, contenu = boite.fetch(num, "(RFC822)")
            if contenu and contenu[0]:
                messages.append(depuis_rfc822(contenu[0][1], "imap"))
        return messages
    finally:
        try:
            boite.logout()
        except Exception:
            pass


# ---------------------------------------------------------------- 1. Microsoft Graph
_etat_connexion = {"en_cours": False, "code": None, "url": None, "message": "", "erreur": None}
_verrou = threading.Lock()


def graph_configure():
    return bool(os.getenv("MS_CLIENT_ID"))


def _application_msal():
    import msal  # import ici pour ne pas bloquer l'appli si le module manque

    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_MSAL):
        with open(CACHE_MSAL, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    app = msal.PublicClientApplication(
        os.getenv("MS_CLIENT_ID"),
        authority="https://login.microsoftonline.com/consumers",  # comptes personnels (Hotmail/Outlook.com)
        token_cache=cache,
    )
    return app, cache


def _sauver_cache(cache):
    if cache.has_state_changed:
        os.makedirs(DOSSIER_DATA, exist_ok=True)
        with open(CACHE_MSAL, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def jeton_graph():
    """Retourne un jeton d'accès valide, ou None s'il faut d'abord se connecter."""
    if not graph_configure():
        return None
    app, cache = _application_msal()
    comptes = app.get_accounts()
    if not comptes:
        return None
    res = app.acquire_token_silent(SCOPES_GRAPH, account=comptes[0])
    _sauver_cache(cache)
    return res.get("access_token") if res else None


def compte_graph():
    if not graph_configure():
        return None
    app, _ = _application_msal()
    comptes = app.get_accounts()
    return comptes[0].get("username") if comptes else None


def demarrer_connexion_graph():
    """Lance la connexion "par code" : l'utilisateur va sur microsoft.com/devicelogin et tape le code."""
    with _verrou:
        if _etat_connexion["en_cours"]:
            return dict(_etat_connexion)
        app, cache = _application_msal()
        flow = app.initiate_device_flow(scopes=SCOPES_GRAPH)
        if "user_code" not in flow:
            _etat_connexion.update(en_cours=False, erreur=str(flow.get("error_description", flow)))
            return dict(_etat_connexion)
        _etat_connexion.update(en_cours=True, code=flow["user_code"], url=flow["verification_uri"],
                               message="", erreur=None)

    def attendre():
        res = app.acquire_token_by_device_flow(flow)  # attend que l'utilisateur ait validé
        _sauver_cache(cache)
        with _verrou:
            if "access_token" in res:
                _etat_connexion.update(en_cours=False, message="Connexion réussie.", code=None)
            else:
                _etat_connexion.update(en_cours=False, code=None,
                                       erreur=res.get("error_description", "Connexion refusée ou expirée."))

    threading.Thread(target=attendre, daemon=True).start()
    return dict(_etat_connexion)


def etat_connexion_graph():
    with _verrou:
        return dict(_etat_connexion)


def lire_graph(depuis, max_messages=500):
    """Lit les e-mails reçus depuis la date donnée (tous dossiers de la boîte de réception)."""
    jeton = jeton_graph()
    if not jeton:
        raise RuntimeError("Outlook non connecté : allez sur la page Import et cliquez sur « Connecter Outlook ».")
    url = "https://graph.microsoft.com/v1.0/me/messages"
    params = {
        "$filter": f"receivedDateTime ge {depuis.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "$select": "id,internetMessageId,subject,from,receivedDateTime,body",
        "$orderby": "receivedDateTime desc",
        "$top": "50",
    }
    entetes = {"Authorization": f"Bearer {jeton}", "Prefer": 'outlook.body-content-type="html"'}
    messages = []
    while url and len(messages) < max_messages:
        r = requests.get(url, headers=entetes, params=params, timeout=30)
        r.raise_for_status()
        donnees = r.json()
        for m in donnees.get("value", []):
            adresse = ((m.get("from") or {}).get("emailAddress") or {})
            corps = m.get("body") or {}
            messages.append({
                "id": m.get("internetMessageId") or m["id"],
                "subject": m.get("subject") or "",
                "from": f"{adresse.get('name', '')} <{adresse.get('address', '')}>",
                "date": (m.get("receivedDateTime") or "")[:16].replace("T", " "),
                "html": corps.get("content", "") if corps.get("contentType") == "html" else "",
                "text": corps.get("content", "") if corps.get("contentType") != "html" else "",
                "origine": "outlook",
            })
        url = donnees.get("@odata.nextLink")
        params = None  # le lien "suivant" contient déjà les paramètres
    return messages


def date_depart(derniere_date, jours_historique):
    """Date à partir de laquelle chercher : dernier import - 1 jour, ou N jours en arrière."""
    if derniere_date:
        try:
            return datetime.strptime(derniere_date[:10], "%Y-%m-%d") - timedelta(days=1)
        except ValueError:
            pass
    return datetime.now() - timedelta(days=jours_historique)


def envoyer_a_soi(sujet, corps):
    """Envoie un e-mail à votre propre adresse (même compte et même mot de passe d'application que l'IMAP)."""
    import smtplib
    from email.message import EmailMessage
    moi = os.getenv("IMAP_USER")
    hote = os.getenv("SMTP_HOST") or (os.getenv("IMAP_HOST") or "").replace("imap.", "smtp.", 1)
    msg = EmailMessage()
    msg["From"] = msg["To"] = moi
    msg["Subject"] = sujet
    msg.set_content(corps)
    with smtplib.SMTP_SSL(hote, 465, timeout=30) as smtp:
        smtp.login(moi, os.getenv("IMAP_PASSWORD"))
        smtp.send_message(msg)
