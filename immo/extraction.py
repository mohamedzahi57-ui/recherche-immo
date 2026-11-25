"""Extraction des annonces contenues dans un e-mail d'alerte.

Principe (aucun accès aux sites : on lit seulement l'e-mail reçu) :
  1. on repère dans l'e-mail les liens qui pointent vers une annonce
     (atHome, Immotop, Wortimmo, SeLoger, Immoweb...) ;
  2. pour chaque lien, on prend le "bloc" de l'e-mail qui l'entoure
     (la vignette de l'annonce) ;
  3. dans le texte de ce bloc, on cherche prix, surface, chambres, commune,
     garage, terrasse, etc. avec des expressions régulières.

Les formats d'e-mails changent parfois : si un champ n'est pas reconnu,
il reste vide et vous pouvez le corriger à la main sur la fiche du bien.
"""
import base64
import hashlib
import json
import re
from urllib.parse import unquote, urlparse, parse_qs

from bs4 import BeautifulSoup

from . import communes

# Reconnaissance des liens d'annonces : (nom de la source, motif de l'URL avec l'identifiant)
MOTIFS_ANNONCES = [
    # atHome : ".../id-9449010.html" (les liens ".../agence/544708" ne sont pas des annonces)
    ("atHome", re.compile(r"athome\.(?:lu|de)/(?:[\w-]+/)*id-(\d{6,})", re.I)),
    ("Immotop", re.compile(r"immotop\.lu/(?:\w+/)*?annonces?/(\d{5,})", re.I)),
    ("Wortimmo", re.compile(r"wortimmo\.lu/.*?(\d{5,})", re.I)),
    ("SeLoger", re.compile(r"seloger\.com/annonces/.*?(\d{6,})", re.I)),
    ("Leboncoin", re.compile(r"leboncoin\.fr/(?:ad/)?\w+/(\d{6,})", re.I)),
    ("Bien'ici", re.compile(r"bienici\.com/annonce/[\w-]*?([\w-]*\d{5,}[\w-]*)", re.I)),
    ("Logic-Immo", re.compile(r"logic-immo\.com/.*?(\d{6,})", re.I)),
    ("Immoweb", re.compile(r"immoweb\.be/.*?/(\d{6,})", re.I)),
    ("Zimmo", re.compile(r"zimmo\.be/.*?/([A-Z0-9]{5,})", re.I)),
]

RE_PRIX = re.compile(
    r"(?:€|EUR)\s*(\d{1,3}(?:[ .,'  ]\d{3})+|\d{5,7})"
    r"|(\d{1,3}(?:[ .,'  ]\d{3})+|\d{5,7})\s*(?:€|EUR|euros?)(?!\s*/\s*m)",
    re.I,
)
# "120 m²", "120m2" ou "120 m 2" (atHome écrit le 2 en exposant, séparé par un espace)
RE_SURFACE = re.compile(r"(\d{2,4}(?:[,.]\d{1,2})?)\s*m\s?(?:²|2|²)(?!\s*de\s*terrain)", re.I)
# Vignette atHome : "Maison - 3 chambres - 120 m 2 Errouville" -> la commune suit la surface
RE_COMMUNE_ATHOME = re.compile(r"\d\s*m\s?(?:²|2)\s+([A-ZÀ-Ý][\w'’ÀÂÄÇÉÈÊËÎÏÔÖÙÛÜà-ÿ.-]*(?:[ -][\w'’À-ÿ.-]+){0,5})")
RE_CHAMBRES = re.compile(r"(\d{1,2})\s*(?:chambres?|ch\b\.?|chb\.?|bedrooms?|slaapkamers?|zimmer)", re.I)
RE_ETAGE = re.compile(r"(\d{1,2})\s*(?:er|e|ème|eme|è)\s*étage|étage\s*:?\s*(\d{1,2})", re.I)
RE_CP = re.compile(r"\b(?:L-?\s?)?(\d{4,5})\b")


def _nombre(txt):
    """'450 000' / '450.000' / '450,000' -> 450000.0"""
    return float(re.sub(r"[ .,'  ]", "", txt))


def _url_mandrill(url):
    """Liens de suivi Mandrill (utilisés par atHome) : la vraie adresse est cachée,
    encodée en base64, dans le paramètre p=. On la décode sans rien télécharger."""
    if "mandrillapp.com/track" not in url:
        return None
    p = parse_qs(urlparse(url).query).get("p", [""])[0]
    try:
        externe = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
        return json.loads(externe["p"]).get("url")
    except (ValueError, KeyError, TypeError):
        return None


def deballer_url(url):
    """Les e-mails utilisent souvent des liens de suivi (redirections).
    On essaie de retrouver la vraie adresse de l'annonce cachée dedans."""
    if not url:
        return ""
    url = url.strip()
    for _ in range(3):
        cible = _url_mandrill(url)
        if cible:
            url = cible
            continue
        dec = unquote(url)
        # paramètre contenant une URL (url=, u=, redirect=, target=...)
        q = parse_qs(urlparse(dec).query)
        cible = None
        for valeurs in q.values():
            for v in valeurs:
                if v.startswith("http"):
                    cible = v
                    break
        if cible and cible != url:
            url = cible
            continue
        # URL encodée au milieu du chemin
        m = re.search(r"https?://[^\s\"'<>]+", dec[8:])
        if m and any(k in m.group(0) for k in ("athome", "immotop", "wortimmo", "seloger", "immoweb")):
            url = m.group(0)
            continue
        return dec
    return url


# Immotop chiffre ses liens (clicks.immotop.lu/f/a/...) : impossible d'y lire l'identifiant
# sans ouvrir le lien (et le site bloque les robots). On reconnaît alors l'annonce au texte
# de son lien, ex. "Appartement 2 chambres 87, Route d'Arlon, Strassen".
RE_LIEN_IMMOTOP = re.compile(r"^https?://clicks\.immotop\.lu/", re.I)
RE_TITRE_ANNONCE = re.compile(r"\b(?:appartement|maison|studio|duplex|penthouse|villa|bungalow|loft|"
                              r"triplex|terrain|chambres?)\b", re.I)


def _cle_immotop_par_href(soup):
    """Associe chaque lien chiffré Immotop à une annonce, d'après le texte du lien titre.
    Le bouton "VOIR LES DÉTAILS" a le même lien que le titre : il retrouve la même annonce."""
    cles = {}
    for a in soup.find_all("a", href=True):
        if not RE_LIEN_IMMOTOP.match(a["href"]):
            continue
        titre = " ".join(a.get_text(" ").replace("﻿", " ").split())
        if titre and RE_TITRE_ANNONCE.search(titre) and a["href"] not in cles:
            empreinte = hashlib.sha1(titre.lower().encode("utf-8")).hexdigest()[:12]
            cles[a["href"]] = ("Immotop", "t-" + empreinte)
    return cles


def identifier_annonce(url):
    """Retourne (source, identifiant) si l'URL est une annonce reconnue, sinon (None, None)."""
    for source, motif in MOTIFS_ANNONCES:
        m = motif.search(url)
        if m:
            return source, m.group(1)
    return None, None


def analyser_texte(texte, url=""):
    """Analyse le texte d'une vignette d'annonce et retourne un dictionnaire de champs."""
    # ﻿ / ​ : caractères invisibles collés aux mots dans certains e-mails (Immotop)
    t = " ".join(re.sub("[﻿​‌‍]", " ", texte or "").split())
    tl = t.lower()
    champs = {}

    # Prix : on garde la première valeur plausible (20 000 à 5 000 000 EUR)
    for m in RE_PRIX.finditer(t):
        brut = m.group(1) or m.group(2)
        try:
            v = _nombre(brut)
        except ValueError:
            continue
        if 20000 <= v <= 5_000_000:
            champs["prix"] = v
            break

    # Surface habitable : première valeur entre 15 et 1000 m² (hors "terrain")
    for m in RE_SURFACE.finditer(t):
        avant = tl[max(0, m.start() - 25):m.start()]
        if "terrain" in avant or "/m" in tl[m.end():m.end() + 2]:
            continue
        v = float(m.group(1).replace(",", "."))
        if 15 <= v <= 1000:
            champs["surface"] = v
            break

    m = RE_CHAMBRES.search(t)
    if m:
        champs["chambres"] = int(m.group(1))
    elif re.search(r"\bstudio\b", tl):
        champs["chambres"] = 0

    # Type de bien
    # (\b = mot entier : "chaussée" ne doit pas être lu comme "haus")
    re_maison = r"\b(?:maison|villa|bungalow|house|haus|pavillon|fermette)\b|plain[- ]pied"
    re_appart = r"\b(?:appartement|appart|duplex|penthouse|studio|flat|wohnung)\b|rez[- ]de[- ]jardin"
    if re.search(r"\b(?:terrain|bauland|grundstück)\b", tl) and not re.search(re_maison + "|" + re_appart, tl):
        champs["type_bien"] = "terrain"
    elif re.search(re_appart, tl):
        champs["type_bien"] = "appartement"
    elif re.search(re_maison, tl):
        champs["type_bien"] = "maison"
    elif "maison" in url.lower():
        champs["type_bien"] = "maison"
    elif "appartement" in url.lower():
        champs["type_bien"] = "appartement"

    # Étage / rez-de-chaussée / plain-pied
    if re.search(r"rez[- ]de[- ]chauss[ée]e|\brdc\b|rez[- ]de[- ]jardin|ground floor", tl):
        champs["rez_de_chaussee"] = 1
        champs["etage"] = "RDC"
    else:
        m = RE_ETAGE.search(t)
        if m:
            champs["etage"] = m.group(1) or m.group(2)
            champs["rez_de_chaussee"] = 0
    if re.search(r"plain[- ]pied|bungalow|de plain pied", tl):
        champs["plain_pied"] = 1

    # Équipements (on ne met 1 que si c'est mentionné ; sinon inconnu)
    if re.search(r"garage|box ferm", tl):
        champs["garage"] = 1
    if re.search(r"parking|emplacement|stationnement|carport", tl):
        champs["parking"] = 1
    if re.search(r"terrasse|balcon|loggia|jardin", tl):
        champs["terrasse"] = 1
    if re.search(r"\bneuf\b|neuve|vefa|sur plan|nouvelle construction|new build|neubau", tl):
        champs["neuf"] = 1
    elif re.search(r"\bancien\b|à rénover|a renover|rénovation", tl):
        champs["neuf"] = 0
    if re.search(r"travaux|à rénover|a renover|rafraîchir|rafraichir|à restaurer|renovation", tl):
        champs["travaux"] = 1

    # Commune et pays : dans le texte, puis dans l'URL (souvent "…/esch-sur-alzette/…")
    nom, pays = communes.trouver_commune(t)
    if not nom and url:
        nom, pays = communes.trouver_commune(re.sub(r"[/_.?=&]", " ", url))
    if nom:
        champs["commune"] = nom
        champs["pays"] = pays
    else:
        # Commune hors de nos listes (ex. Trier, Toul) : on garde le nom, sans pays.
        # La géolocalisation trouvera le pays et le bien sera écarté s'il est trop loin.
        m = RE_COMMUNE_ATHOME.search(t)
        if m:
            champs["commune"] = m.group(1).strip(" -.")
    m = re.search(r"\bL-?\s?(\d{4})\b", t)
    if m:
        champs["code_postal"] = "L-" + m.group(1)
        champs.setdefault("pays", "LU")
    return champs


def _bloc_annonce(lien, cles_autres, cles_href=None):
    """Remonte depuis le lien jusqu'au plus petit bloc qui contient un prix,
    sans englober d'autres annonces."""
    meilleur = lien
    noeud = lien
    for _ in range(12):
        parent = noeud.parent
        if parent is None or parent.name in ("body", "html", "[document]"):
            break
        # si le parent contient le lien d'une autre annonce, on s'arrête
        autres = False
        for a in parent.find_all("a", href=True):
            s, i = (cles_href or {}).get(a["href"]) or identifier_annonce(deballer_url(a["href"]))
            if s and (s, i) in cles_autres:
                autres = True
                break
        if autres:
            break
        noeud = parent
        meilleur = parent
        if RE_PRIX.search(parent.get_text(" ")) and RE_SURFACE.search(parent.get_text(" ")):
            break
    return meilleur


def extraire_annonces(message):
    """Prend un e-mail {'html', 'text', 'subject', ...} et retourne la liste des annonces trouvées.
    Chaque annonce : {'source', 'id_externe', 'url', 'texte', + champs analysés}."""
    html = message.get("html") or ""
    texte_brut = message.get("text") or ""
    annonces = {}

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["style", "script", "head"]):
            s.decompose()
        liens = []
        cles_href = _cle_immotop_par_href(soup)
        for a in soup.find_all("a", href=True):
            url = deballer_url(a["href"])
            source, ident = cles_href.get(a["href"]) or identifier_annonce(url)
            if source:
                liens.append((a, url, source, ident))
        cles = {(s, i) for _, _, s, i in liens}
        for a, url, source, ident in liens:
            cle = (source, ident)
            bloc = _bloc_annonce(a, cles - {cle}, cles_href)
            texte = " ".join(bloc.get_text(" ").split())
            if not RE_PRIX.search(texte):
                # Mise en page en lignes séparées (titre puis détails sur la ligne suivante) :
                # on ajoute les éléments suivants jusqu'au lien de l'annonce suivante.
                for voisin in list(bloc.find_next_siblings())[:3]:
                    if any((cles_href.get(x["href"]) or identifier_annonce(deballer_url(x["href"])))[0]
                           for x in voisin.find_all("a", href=True)):
                        break
                    texte += " " + " ".join(voisin.get_text(" ").split())
            if cle in annonces:
                # même annonce présente deux fois (image + titre) : on garde le texte le plus riche
                if len(texte) > len(annonces[cle]["texte"]):
                    annonces[cle]["texte"] = texte
                continue
            annonces[cle] = {"source": source, "id_externe": ident, "url": url, "texte": texte}

    if not annonces and texte_brut:
        # E-mail en texte simple : on découpe autour de chaque lien
        for m in re.finditer(r"https?://\S+", texte_brut):
            url = deballer_url(m.group(0).rstrip(">).,"))
            source, ident = identifier_annonce(url)
            if not source or (source, ident) in annonces:
                continue
            debut = max(0, m.start() - 400)
            texte = texte_brut[debut:m.start()]
            # on ne garde que ce qui suit le lien précédent
            texte = re.split(r"https?://\S+", texte)[-1]
            annonces[(source, ident)] = {"source": source, "id_externe": ident, "url": url, "texte": texte}

    resultat = []
    for a in annonces.values():
        a.update(analyser_texte(a["texte"], a["url"]))
        a["titre"] = _titre(a)
        resultat.append(a)
    return resultat


def _titre(a):
    morceaux = [(a.get("type_bien") or "Bien").capitalize()]
    if a.get("surface"):
        morceaux.append(f"{a['surface']:g} m²")
    if a.get("commune"):
        morceaux.append(a["commune"])
    return " – ".join(morceaux)
