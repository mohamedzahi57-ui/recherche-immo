"""Listes de communes / localités pour reconnaître le lieu et le pays d'une annonce.

Ces listes servent seulement à repérer un nom de lieu dans le texte d'un e-mail.
Les coordonnées GPS sont ensuite demandées à un service de géolocalisation.
Vous pouvez ajouter des noms ici si une commune n'est pas reconnue.
"""
import re
import unicodedata

# Communes et localités courantes du Luxembourg
LU = """
Luxembourg, Luxembourg-Ville, Bonnevoie, Gasperich, Cessange, Merl, Belair, Kirchberg, Limpertsberg,
Hollerich, Bertrange, Strassen, Mamer, Capellen, Kehlen, Steinfort, Koerich, Garnich, Dippach, Bettange-sur-Mess,
Leudelange, Hesperange, Howald, Itzig, Alzingen, Fentange, Sandweiler, Contern, Moutfort, Schuttrange, Munsbach,
Niederanven, Senningerberg, Walferdange, Steinsel, Lorentzweiler, Lintgen, Mersch, Lintgen, Helmsange, Bridel, Kopstal,
Esch-sur-Alzette, Belval, Esch, Differdange, Oberkorn, Niederkorn, Dudelange, Pétange, Rodange, Lamadelaine,
Sanem, Belvaux, Soleuvre, Ehlerange, Schifflange, Kayl, Tétange, Rumelange, Bettembourg, Noertzange, Huncherange,
Mondercange, Pontpierre, Bergem, Reckange-sur-Mess, Roeser, Berchem, Bivange, Crauthem, Peppange, Frisange,
Aspelt, Hellange, Mondorf-les-Bains, Dalheim, Weiler-la-Tour, Remich, Schengen, Bous, Stadtbredimus, Wormeldange,
Grevenmacher, Mertert, Wasserbillig, Flaxweiler, Betzdorf, Biwer, Manternach, Junglinster, Echternach, Rosport,
Mompach, Consdorf, Berdorf, Bech, Heffingen, Larochette, Fischbach, Nommern, Ettelbruck, Diekirch, Erpeldange,
Schieren, Colmar-Berg, Bissen, Boevange-sur-Attert, Helperknapp, Tuntange, Useldange, Redange-sur-Attert, Redange,
Préizerdaul, Vichten, Wahl, Grosbous, Rambrouch, Ell, Beckerich, Saeul, Septfontaines, Habscht, Hobscheid, Eischen,
Clemency, Fingig, Sanem, Käerjeng, Bascharage, Hautcharage, Linger, Wiltz, Vianden, Clervaux, Troisvierges,
Weiswampach, Wincrange, Parc Hosingen, Hosingen, Kiischpelt, Goesdorf, Esch-sur-Sûre, Lac de la Haute-Sûre,
Boulaide, Feulen, Mertzig, Bettendorf, Reisdorf, Beaufort, Vallée de l'Ernz, Waldbillig, Tandel, Putscheid,
Bourscheid, Erpeldange-sur-Sûre, Mondercange, Sandweiler, Weiler, Lenningen, Waldbredimus, Bettembourg,
Strassen, Bereldange, Heisdorf, Mullendorf, Hunsdorf, Pettingen, Haut-Martelange, Rombach-Martelange, Dirbach,
Redange/Attert, Rosport-Mompach
"""

# Communes françaises proches de la frontière luxembourgeoise
FR = """
Audun-le-Tiche, Villerupt, Russange, Ottange, Rédange, Thil, Aumetz, Volmerange-les-Mines, Zoufftgen, Hettange-Grande,
Entrange, Kanfen, Roussy-le-Village, Évrange, Basse-Rentgen, Haute-Rentgen, Hagen, Mondorff, Puttelange-lès-Thionville,
Rodemack, Breistroff-la-Grande, Boust, Cattenom, Sierck-les-Bains, Apach, Manderen, Contz-les-Bains, Haute-Kontz,
Longwy, Mont-Saint-Martin, Longlaville, Herserange, Saulnes, Hussigny-Godbrange, Tiercelet, Crusnes, Errouville,
Thionville, Yutz, Fontoy, Algrange, Escherange, Tressange, Boulange, Basse-Ham, Kœnigsmacker, Koenigsmacker, Gandren,
Beyren-lès-Sierck, Fixem, Œutrange, Oeutrange, Lexy, Réhon, Cutry, Villers-la-Montagne, Morfontaine, Rédange
"""

# Communes belges proches de la frontière luxembourgeoise
BE = """
Arlon, Aubange, Athus, Messancy, Attert, Martelange, Fauvillers, Vaux-sur-Sûre, Bastogne, Gouvy, Burg-Reuland,
Halanzy, Musson, Sélange, Habergy, Toernich, Heinsch, Stockem, Bonnert, Guirsch, Udange, Weyler, Hondelange,
Wolkrange, Turpange, Rachecourt, Autelbas, Barnich, Sterpenich, Nobressart, Thiaumont, Tontelange, Nothomb,
Rombach, Hachy, Fouches, Waltzing, Longlier, Léglise, Habay, Tintigny, Étalle, Saint-Léger
"""


def normaliser(texte):
    """Minuscules, sans accents, tirets/apostrophes remplacés par des espaces."""
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower().replace("œ", "oe")
    texte = re.sub(r"[-'’_/]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _liste(bloc):
    return [n.strip() for n in bloc.replace("\n", " ").split(",") if n.strip()]


# Quartiers de Luxembourg-Ville -> "Luxembourg"
QUARTIERS_LUX = {"bonnevoie", "gasperich", "cessange", "merl", "belair", "kirchberg", "limpertsberg",
                 "hollerich", "luxembourg ville"}

# Localités rattachées à une commune (le quartier Belval est à Esch-sur-Alzette)
LOCALITES = {"belval": "Esch-sur-Alzette", "haut martelange": "Rambrouch", "rombach martelange": "Rambrouch",
             "dirbach": "Goesdorf", "redange attert": "Redange", "rosport mompach": "Rosport-Mompach"}

# « rue de Longwy », « route de Thionville » : un nom de rue, pas la commune du bien
RE_RUE = re.compile(r" (?:rue|route|rte|avenue|av|boulevard|bd|chemin|place|allee|impasse)(?: [a-z]+){0,3} $"
                    # « 23 Michel Rodange, Gare » : numéro + prénom avant le nom = une rue
                    r"| \d{1,3}[a-z]? (?!(?:chambres?|pieces?|ares?|m|a|au|en|et|de)\b)[a-z]+ $")

# Index : nom normalisé -> (nom affiché, pays)
INDEX = {}
for _pays, _bloc in (("FR", FR), ("BE", BE), ("LU", LU)):  # LU en dernier = prioritaire en cas d'homonyme
    for _nom in _liste(_bloc):
        _n = normaliser(_nom)
        affiche = "Luxembourg" if _n in QUARTIERS_LUX else LOCALITES.get(_n, _nom)
        INDEX[_n] = (affiche, _pays)

# Noms triés du plus long au plus court (pour reconnaître "Esch-sur-Alzette" avant "Esch")
_NOMS_TRIES = sorted(INDEX.keys(), key=len, reverse=True)
_MOTS_AMBIGUS = {"esch", "weiler", "ell", "wahl", "thil", "lexy", "hagen", "boust", "fixem"}


def trouver_commune(texte):
    """Cherche une commune connue dans un texte. Retourne (nom, pays) ou (None, None).

    On garde celle qui apparaît EN PREMIER (à égalité, le nom le plus long) : la commune du bien
    vient avant le nom de l'agence (« … à vendre à Ettelbruck … Engel & Völkers LUXEMBOURG »)."""
    # les virgules et parenthèses deviennent le repère « , » ; le reste de la ponctuation disparaît
    t = re.sub(r"[,;()]", " , ", texte or "")
    t = " " + re.sub(r"[^a-z0-9 ,]", " ", normaliser(t)) + " "
    t = re.sub(r" +", " ", t)
    meilleur = None
    for nom in _NOMS_TRIES:
        pos = t.find(f" {nom} ")
        while pos != -1:
            ambigu = nom in _MOTS_AMBIGUS and len(nom) <= 5
            # mots courts : on exige un contexte typique ("à Ell", "Ell (L-...)", etc.)
            contexte_ok = not ambigu or re.search(rf"(?: a | in | l \d{{4}} | \d{{4,5}} ){re.escape(nom)} $",
                                                  t[:pos + len(nom) + 2])
            if contexte_ok and not RE_RUE.search(t[max(0, pos - 40):pos + 1]):
                if meilleur is None or pos < meilleur[0]:
                    meilleur = (pos, nom)
                break
            pos = t.find(f" {nom} ", pos + 1)
    if not meilleur:
        return None, None
    # Format « Bascharage, Käerjeng » / « Erpeldange (Wiltz) » : la localité est suivie de sa
    # commune après une virgule, on garde la commune (sauf « …, Luxembourg » = le pays)
    pos, nom = meilleur
    mots = t[pos + len(nom) + 2:].split(" ")
    i, sautes = 0, 0
    while i < len(mots) and sautes <= 2:
        if mots[i] == ",":
            reste = " ".join(mots[i + 1:])
            for autre in _NOMS_TRIES:
                if autre == "luxembourg" or autre in _MOTS_AMBIGUS or nom.startswith(autre) or autre.startswith(nom):
                    continue  # « Weiler-la-Tour, Weiler-la-Tour » : même lieu répété
                if reste.startswith(autre + " "):
                    return INDEX[autre]
        elif mots[i].isalpha() and len(mots[i]) >= 3:
            sautes += 1  # « Belval Sud-Lycée, Sanem » / « Septfontaines, Simmerschmelz, Habscht »
        else:
            break
        i += 1
    return INDEX[nom]


def pays_de_commune(nom):
    """Pays connu d'une commune (ou None)."""
    res = INDEX.get(normaliser(nom or ""))
    return res[1] if res else None
