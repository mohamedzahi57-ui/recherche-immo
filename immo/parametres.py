"""Paramètres de recherche, modifiables depuis la page "Paramètres".

Chaque paramètre est décrit ici une seule fois : clé, valeur par défaut,
libellé affiché, section de la page, type et aide. La page web est générée
automatiquement à partir de cette liste.
"""
import json

# (clé, valeur par défaut, libellé, section, type, aide)
# types : "int", "float", "bool", "text", "choix:a|b|c"
DEFINITIONS = [
    # --- Critères principaux
    ("prix_max", 500000, "Prix maximum hors frais (EUR)", "Critères", "int", ""),
    ("surface_min_appart", 50, "Surface minimale d'un appartement (m²)", "Critères", "int",
     "Un appartement en rez-de-chaussée est accepté même plus petit."),
    ("accepter_rdc_petit", True, "Accepter un rez-de-chaussée sous cette surface", "Critères", "bool", ""),
    ("maison_plain_pied_obligatoire", False, "Maison : exiger le plain-pied", "Critères", "bool",
     "Si décoché, une maison à étage reste visible mais perd des points."),
    ("chambres_min", 1, "Chambres minimum", "Critères", "int", ""),
    ("chambres_ideal", 2, "Chambres idéal", "Critères", "int", ""),
    ("accepter_travaux", True, "Accepter les biens avec travaux", "Critères", "bool", ""),
    ("accepter_terrains", False, "Afficher les terrains (module V3)", "Critères", "bool", ""),
    # --- Zone géographique
    ("pays_actifs", "LU,FR,BE", "Pays recherchés (LU,FR,BE)", "Zone", "text", "Ordre = priorité."),
    ("distance_frontiere_max_km", 5.0, "France/Belgique : distance max à la frontière (km)", "Zone", "float",
     "Distance calculée avec un tracé simplifié de la frontière (précision ~1-2 km)."),
    # --- Travail et trajets
    # (l'adresse exacte est enregistrée dans la base, pas dans le code publié)
    ("travail_adresse", "Leudelange, Luxembourg", "Adresse du travail", "Trajets", "text", ""),
    ("travail_lat", 49.5654, "Latitude du travail", "Trajets", "float",
     "Recalculée automatiquement depuis l'adresse (bouton sur cette page)."),
    ("travail_lon", 6.0811, "Longitude du travail", "Trajets", "float", ""),
    ("trajet_max_min", 45, "Temps de trajet maximum (minutes)", "Trajets", "int", ""),
    ("regle_trajet", "voiture", "Règle d'exclusion sur le trajet", "Trajets",
     "choix:voiture|les_deux|l_un_ou_l_autre",
     "voiture = la voiture doit être sous le maximum ; les_deux = voiture ET transports ; "
     "l_un_ou_l_autre = au moins un des deux."),
    ("majoration_trafic_pct", 25, "Majoration heure de pointe sur la voiture (%)", "Trajets", "int",
     "OpenRouteService ne connaît pas les bouchons : on ajoute ce pourcentage."),
    ("heure_arrivee", "08:30", "Heure d'arrivée souhaitée au travail (transports)", "Trajets", "text", ""),
    # --- Frais Luxembourg
    ("lu_droits_enregistrement_pct", 6.0, "LU : droits d'enregistrement (%)", "Frais Luxembourg", "float", ""),
    ("lu_transcription_pct", 1.0, "LU : droits de transcription (%)", "Frais Luxembourg", "float", ""),
    ("lu_notaire_pct", 1.0, "LU : honoraires de notaire (%)", "Frais Luxembourg", "float", ""),
    ("lu_residence_principale", True, "LU : résidence principale (Bëllegen Akt)", "Frais Luxembourg", "bool", ""),
    ("lu_bellegen_akt_par_acheteur", 40000, "LU : Bëllegen Akt par acheteur (EUR)", "Frais Luxembourg", "int",
     "Montant à vérifier chaque année sur guichet.lu. Il ne peut pas dépasser les droits "
     "d'enregistrement + transcription."),
    ("lu_nb_acheteurs", 1, "LU : nombre d'acheteurs", "Frais Luxembourg", "int", ""),
    # --- Frais France / Belgique
    ("fr_frais_ancien_pct", 8.0, "France : frais d'acquisition, ancien (%)", "Frais France / Belgique", "float",
     "Droits de mutation + notaire, environ 7 à 8 %."),
    ("fr_frais_neuf_pct", 3.0, "France : frais d'acquisition, neuf (%)", "Frais France / Belgique", "float", ""),
    ("be_frais_pct", 6.0, "Belgique : frais d'acquisition (%)", "Frais France / Belgique", "float",
     "Wallonie, habitation propre et unique : droits 3 % (depuis 2025) + notaire/TVA/frais. À vérifier."),
    # --- Import
    ("import_auto", True, "Import automatique des e-mails", "Import", "bool", ""),
    ("import_intervalle_heures", 4, "Intervalle entre deux imports (heures)", "Import", "int", ""),
    ("import_jours_historique", 30, "Au premier import, remonter de N jours", "Import", "int", ""),
    ("expediteurs_alertes",
     "athome.lu,immotop.lu,wortimmo.lu,seloger.com,leboncoin.fr,bienici.com,logic-immo.com,immoweb.be,zimmo.be",
     "Domaines des expéditeurs d'alertes", "Import", "text",
     "Seuls les e-mails venant de ces domaines sont lus."),
    # --- Pondération du score (total conseillé = 100)
    ("poids_pays", 20, "Score : pays (LU plein, FR moitié, BE quart)", "Score", "int", ""),
    ("poids_chambres", 20, "Score : chambres (2 = plein, 1 = 40 %)", "Score", "int", ""),
    ("poids_garage", 15, "Score : garage (parking = 2/3)", "Score", "int", ""),
    ("poids_terrasse", 5, "Score : terrasse", "Score", "int", ""),
    ("poids_trajet_voiture", 15, "Score : trajet voiture court", "Score", "int", ""),
    ("poids_trajet_tc", 10, "Score : trajet transports ≤ maximum", "Score", "int", ""),
    ("poids_prix", 10, "Score : prix bas par rapport au maximum", "Score", "int", ""),
    ("poids_type", 5, "Score : plain-pied / rez-de-chaussée", "Score", "int", ""),
]

DEFAUTS = {d[0]: d[1] for d in DEFINITIONS}
TYPES = {d[0]: d[4] for d in DEFINITIONS}


def _convertir(cle, valeur):
    """Convertit une valeur saisie (texte) dans le bon type."""
    t = TYPES.get(cle, "text")
    if t == "bool":
        if isinstance(valeur, bool):
            return valeur
        return str(valeur).lower() in ("1", "true", "on", "oui", "yes")
    if t == "int":
        return int(float(str(valeur).replace(",", ".").replace(" ", "")))
    if t == "float":
        return float(str(valeur).replace(",", ".").replace(" ", ""))
    return str(valeur).strip()


def lire(conn):
    """Retourne tous les paramètres (valeurs enregistrées sinon valeurs par défaut)."""
    p = dict(DEFAUTS)
    for row in conn.execute("SELECT cle, valeur FROM parametres"):
        if row["cle"] in p:
            try:
                p[row["cle"]] = json.loads(row["valeur"])
            except (ValueError, TypeError):
                pass
    return p


def ecrire(conn, valeurs):
    """Enregistre un dictionnaire {clé: valeur} (seules les clés connues sont gardées)."""
    for cle, valeur in valeurs.items():
        if cle not in DEFAUTS:
            continue
        conn.execute(
            "INSERT INTO parametres(cle, valeur) VALUES(?, ?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
            (cle, json.dumps(_convertir(cle, valeur))),
        )
    conn.commit()


def depuis_formulaire(form):
    """Transforme le formulaire web en dictionnaire de paramètres.
    Les cases à cocher non cochées n'apparaissent pas dans le formulaire : on les met à False."""
    valeurs = {}
    for cle, _defaut, _lib, _sec, t, _aide in DEFINITIONS:
        if t == "bool":
            valeurs[cle] = cle in form
        elif cle in form and str(form[cle]).strip() != "":
            valeurs[cle] = form[cle]
    return valeurs


def sections():
    """Paramètres regroupés par section, pour l'affichage de la page."""
    res = {}
    for d in DEFINITIONS:
        res.setdefault(d[3], []).append(d)
    return res
