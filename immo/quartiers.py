"""Quartier de Luxembourg-ville, retrouvé dans le texte des annonces.

atHome écrit « à vendre à Luxembourg-Hollerich », Immotop « Studio, Hollerich, Luxembourg ».
On ne cherche le quartier que juste à côté du mot Luxembourg, pour ne pas confondre
avec une phrase comme « proche de la gare ».
"""
import re
import unicodedata

# nom affiché : variantes écrites dans les annonces (sans accents, en minuscules)
QUARTIERS = {
    "Centre (Ville-Haute)": ["ville-haute", "ville haute", "centre-ville", "centre ville", "centre", "oberstadt"],
    "Gare": ["gare", "bahnhof"],
    "Limpertsberg": ["limpertsberg"],
    "Belair": ["belair", "bel-air"],
    "Rollingergrund": ["rollingergrund", "rollingergrund-belair nord", "belair-nord", "belair nord"],
    "Grund": ["grund"],
    "Clausen": ["clausen"],
    "Pfaffenthal": ["pfaffenthal"],
    "Kirchberg": ["kirchberg"],
    "Weimerskirch": ["weimerskirch"],
    "Eich": ["eich"],
    "Dommeldange": ["dommeldange"],
    "Beggen": ["beggen"],
    "Mühlenbach": ["muhlenbach", "muehlenbach"],
    "Neudorf-Weimershof": ["neudorf", "weimershof", "neudorf-weimershof"],
    "Cents": ["cents"],
    "Pulvermühl": ["pulvermuhl", "pulvermuehl"],
    "Hamm": ["hamm"],
    "Bonnevoie": ["bonnevoie", "bonnevoie-nord", "bonnevoie-sud", "bonnevoie nord", "bonnevoie sud",
                  "verlorenkost", "bonnevoie-nord-verlorenkost"],
    "Hollerich": ["hollerich"],
    "Gasperich / Cloche d'Or": ["gasperich", "cloche d'or", "cloche dor", "gasperich-cloche d'or",
                                "gasperich-cloche dor", "ban de gasperich"],
    "Cessange": ["cessange"],
    "Merl": ["merl"],
}
_VARIANTES = sorted(((v, nom) for nom, vs in QUARTIERS.items() for v in vs), key=lambda x: -len(x[0]))
_ALT = "|".join(re.escape(v) for v, _ in _VARIANTES)
_NOMS = dict(_VARIANTES)
# « Luxembourg-Hollerich », « Luxembourg - Gare », « Luxembourg (Kirchberg) »
RE_APRES = re.compile(rf"luxembourg\s*[-–(/,]\s*({_ALT})(?![a-z])")
# « Hollerich, Luxembourg », « Hollerich - Luxembourg »
RE_AVANT = re.compile(rf"(?<![a-z])({_ALT})\s*[,-–]\s*luxembourg")


def _simplifier(texte):
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[’`]", "'", t)


def trouver(*textes):
    """Nom du quartier, ou None."""
    for texte in textes:
        t = _simplifier(texte)
        m = RE_APRES.search(t) or RE_AVANT.search(t)
        if m:
            return _NOMS[m.group(1)]
    return None


def est_luxembourg_ville(commune):
    return _simplifier(commune).strip() in ("luxembourg", "luxembourg-ville", "luxembourg ville", "ville de luxembourg")
