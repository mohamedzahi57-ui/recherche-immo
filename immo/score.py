"""Vérification des critères et score de pertinence (0 à 100).

Deux choses distinctes :
  * "hors critères" : raisons qui excluent un bien (prix trop élevé, trop loin...).
    Ces biens restent en base mais sont masqués par défaut dans la liste.
  * le score : plus il est élevé, plus le bien correspond à vos priorités.
    Le détail des points est affiché sur la fiche du bien.
Une information inconnue (ex. garage non mentionné) ne fait pas exclure le bien.
"""


def verifier_criteres(b, p):
    """Retourne la liste des raisons pour lesquelles le bien est hors critères."""
    raisons = []
    pays_actifs = [x.strip().upper() for x in p["pays_actifs"].split(",") if x.strip()]

    type_bien = b.get("type_bien")
    pmax = p["prix_max_terrain"] if type_bien == "terrain" else p["prix_max"]
    if b.get("prix") and b["prix"] > pmax:
        raisons.append(f"prix {b['prix']:,.0f} € > {pmax:,} €".replace(",", " "))
    if b.get("pays") and b["pays"] not in pays_actifs:
        raisons.append(f"pays {b['pays']} non recherché")
    if b.get("pays") in ("FR", "BE") and b.get("distance_frontiere_km") is not None \
            and b["distance_frontiere_km"] > p["distance_frontiere_max_km"]:
        raisons.append(f"à {b['distance_frontiere_km']:g} km de la frontière")
    if b.get("chambres") is not None and b["chambres"] < p["chambres_min"]:
        raisons.append(f"{b['chambres']} chambre(s)")
    if b.get("travaux") and not p["accepter_travaux"]:
        raisons.append("travaux")

    if type_bien == "terrain" and not p["accepter_terrains"]:
        raisons.append("terrain non recherché")
    if type_bien == "terrain" and "non constructible" in ((b.get("description") or "") + (b.get("titre") or "")).lower():
        raisons.append("terrain non constructible")
    if type_bien == "appartement" and b.get("surface") and b["surface"] < p["surface_min_appart"]:
        if not (b.get("rez_de_chaussee") and p["accepter_rdc_petit"]):
            raisons.append(f"appartement de {b['surface']:g} m² < {p['surface_min_appart']} m²")
    if type_bien == "maison" and p["maison_plain_pied_obligatoire"] and b.get("plain_pied") != 1:
        raisons.append("maison non plain-pied")

    # Trajet
    tmax = p["trajet_max_min"]
    v, tc = b.get("trajet_voiture_min"), b.get("trajet_tc_min")
    v_ok = v is None or v <= tmax
    tc_ok = tc is None or tc <= tmax
    regle = p["regle_trajet"]
    if regle == "voiture" and not v_ok:
        raisons.append(f"voiture {v:g} min > {tmax} min")
    elif regle == "les_deux" and not (v_ok and tc_ok):
        raisons.append(f"trajet > {tmax} min (voiture {v} / transports {tc})")
    elif regle == "l_un_ou_l_autre" and not (v_ok or tc_ok):
        raisons.append(f"voiture et transports > {tmax} min")
    return raisons


def calculer_score(b, p):
    """Retourne (score sur 100, détail [(libellé, points, max)])."""
    detail = []

    # Pays (priorité LU > FR > BE)
    part = {"LU": 1.0, "FR": 0.5, "BE": 0.25}.get(b.get("pays"), 0.0)
    detail.append(("Pays", p["poids_pays"] * part, p["poids_pays"]))

    # Chambres
    ch = b.get("chambres")
    if ch is None:
        part = 0.4
    elif ch >= p["chambres_ideal"]:
        part = 1.0
    elif ch >= p["chambres_min"]:
        part = 0.4
    else:
        part = 0.0
    detail.append(("Chambres", p["poids_chambres"] * part, p["poids_chambres"]))

    # Garage > parking
    part = 1.0 if b.get("garage") else (2 / 3 if b.get("parking") else 0.0)
    detail.append(("Garage / parking", p["poids_garage"] * part, p["poids_garage"]))

    detail.append(("Terrasse", p["poids_terrasse"] * (1.0 if b.get("terrasse") else 0.0), p["poids_terrasse"]))

    # Trajet voiture : plein à 15 min ou moins, 0 au-delà du maximum
    v, tmax = b.get("trajet_voiture_min"), p["trajet_max_min"]
    if v is None:
        part = 0.3
    elif v <= 15:
        part = 1.0
    elif v <= tmax:
        part = 1.0 - 0.7 * (v - 15) / max(1, tmax - 15)
    else:
        part = 0.0
    detail.append(("Trajet voiture", p["poids_trajet_voiture"] * part, p["poids_trajet_voiture"]))

    # Trajet transports
    tc = b.get("trajet_tc_min")
    if tc is None:
        part = 0.3
    elif tc <= tmax:
        part = 1.0
    elif tc <= tmax + 15:
        part = 0.4
    else:
        part = 0.0
    detail.append(("Trajet transports", p["poids_trajet_tc"] * part, p["poids_trajet_tc"]))

    # Prix : plein si 30 % sous le maximum ou moins, 0 au maximum
    prix = b.get("prix")
    if prix:
        pmax = p["prix_max_terrain"] if b.get("type_bien") == "terrain" else p["prix_max"]
        part = max(0.0, min(1.0, (pmax - prix) / (0.3 * pmax)))
    else:
        part = 0.0
    detail.append(("Prix", p["poids_prix"] * part, p["poids_prix"]))

    # Plain-pied / rez-de-chaussée
    # (un terrain permet de construire de plain-pied)
    part = 1.0 if (b.get("plain_pied") or b.get("rez_de_chaussee") or b.get("type_bien") == "terrain") else 0.0
    detail.append(("Plain-pied / RDC", p["poids_type"] * part, p["poids_type"]))

    total = sum(pts for _, pts, _ in detail)
    maxi = sum(m for _, _, m in detail) or 1
    return round(100 * total / maxi), [(lib, round(pts, 1), m) for lib, pts, m in detail]
