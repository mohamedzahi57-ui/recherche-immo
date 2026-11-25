"""Géolocalisation, distance à la frontière et temps de trajet.

Services utilisés (tous gratuits) :
  * Géolocalisation : OpenRouteService si une clé est fournie, sinon Nominatim
    (OpenStreetMap, sans clé, limité à 1 requête par seconde).
  * Voiture : OpenRouteService (clé gratuite, 2 000 calculs/jour).
    Sans clé : estimation à vol d'oiseau (marquée "estimation").
  * Transports en commun : API mobiliteit.lu (clé gratuite sur demande),
    qui couvre aussi les trains et bus transfrontaliers vers le Luxembourg.
Tous les résultats sont gardés en mémoire (tables geocache et trajets_cache)
pour ne jamais redemander deux fois la même chose.
"""
import math
import os
import re
import time
from datetime import datetime, timedelta

import requests

from .db import maintenant

AGENT = "RechercheImmoPersonnelle/1.0 (usage prive)"
_dernier_appel_nominatim = [0.0]

# Tracé simplifié de la frontière du Luxembourg (longitude, latitude), sens horaire.
# Précision d'environ 1 à 2 km : suffisant pour un critère "à 5 km de la frontière".
FRONTIERE_LU = [
    (6.027, 50.182), (6.090, 50.170), (6.137, 50.128), (6.117, 50.060), (6.140, 50.020),
    (6.170, 49.990), (6.210, 49.940), (6.260, 49.880), (6.320, 49.840), (6.430, 49.810),
    (6.520, 49.730), (6.505, 49.710), (6.440, 49.680), (6.420, 49.640), (6.370, 49.590),
    (6.370, 49.550), (6.360, 49.470), (6.280, 49.495), (6.240, 49.505), (6.190, 49.505),
    (6.150, 49.500), (6.100, 49.460), (6.030, 49.450), (5.980, 49.460), (5.940, 49.495),
    (5.900, 49.500), (5.840, 49.530), (5.818, 49.546), (5.870, 49.580), (5.900, 49.640),
    (5.890, 49.670), (5.870, 49.710), (5.830, 49.740), (5.780, 49.790), (5.750, 49.830),
    (5.750, 49.880), (5.780, 49.930), (5.820, 49.970), (5.870, 50.050), (5.950, 50.120),
    (6.000, 50.160), (6.027, 50.182),
]

PAYS_ISO = {"lu": "LU", "lux": "LU", "fr": "FR", "fra": "FR", "be": "BE", "bel": "BE",
            "de": "DE", "deu": "DE"}
NOMS_PAYS = {"LU": "Luxembourg", "FR": "France", "BE": "Belgique"}


# ---------------------------------------------------------------- distances
def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau (formule de haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def dans_luxembourg(lat, lon):
    """Le point est-il à l'intérieur du tracé du Luxembourg ? (test du rayon)"""
    dedans = False
    pts = FRONTIERE_LU
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x:
                dedans = not dedans
    return dedans


def distance_frontiere_km(lat, lon):
    """Distance (km) entre un point hors du Luxembourg et la frontière luxembourgeoise.
    Retourne 0 si le point est au Luxembourg."""
    if dans_luxembourg(lat, lon):
        return 0.0
    kx = 111.32 * math.cos(math.radians(lat))  # km par degré de longitude à cette latitude
    ky = 110.57
    meilleur = float("inf")
    for (x1, y1), (x2, y2) in zip(FRONTIERE_LU, FRONTIERE_LU[1:]):
        ax, ay = (x1 - lon) * kx, (y1 - lat) * ky
        bx, by = (x2 - lon) * kx, (y2 - lat) * ky
        dx, dy = bx - ax, by - ay
        long2 = dx * dx + dy * dy
        t = 0 if long2 == 0 else max(0, min(1, -(ax * dx + ay * dy) / long2))
        px, py = ax + t * dx, ay + t * dy
        meilleur = min(meilleur, math.hypot(px, py))
    return round(meilleur, 1)


# ---------------------------------------------------------------- géolocalisation
def geolocaliser(conn, requete):
    """Adresse/commune -> (lat, lon, pays) ou (None, None, None). Résultat mémorisé."""
    cle = requete.strip().lower()
    row = conn.execute("SELECT lat, lon, pays FROM geocache WHERE requete = ?", (cle,)).fetchone()
    if row:
        return row["lat"], row["lon"], row["pays"]

    lat = lon = pays = None
    try:
        if os.getenv("ORS_API_KEY"):
            r = requests.get(
                "https://api.openrouteservice.org/geocode/search",
                params={"api_key": os.getenv("ORS_API_KEY"), "text": requete,
                        "boundary.country": "LU,FR,BE,DE", "size": 1},
                headers={"User-Agent": AGENT}, timeout=20)
            r.raise_for_status()
            feats = r.json().get("features") or []
            if feats:
                lon, lat = feats[0]["geometry"]["coordinates"]
                pays = PAYS_ISO.get((feats[0]["properties"].get("country_a") or "").lower())
        else:
            # Nominatim : 1 requête par seconde maximum (règle d'utilisation)
            attente = 1.1 - (time.time() - _dernier_appel_nominatim[0])
            if attente > 0:
                time.sleep(attente)
            _dernier_appel_nominatim[0] = time.time()
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": requete, "format": "jsonv2", "limit": 1, "addressdetails": 1,
                        "countrycodes": "lu,fr,be,de"},
                headers={"User-Agent": AGENT}, timeout=20)
            r.raise_for_status()
            res = r.json()
            if res:
                lat, lon = float(res[0]["lat"]), float(res[0]["lon"])
                pays = PAYS_ISO.get(((res[0].get("address") or {}).get("country_code") or "").lower())
    except requests.RequestException as e:
        print(f"[geo] échec géolocalisation '{requete}': {e}")
        return None, None, None  # pas mémorisé : on réessaiera plus tard

    conn.execute("INSERT OR REPLACE INTO geocache(requete, lat, lon, pays, date) VALUES (?,?,?,?,?)",
                 (cle, lat, lon, pays, maintenant()))
    conn.commit()
    return lat, lon, pays


# ---------------------------------------------------------------- trajets
def _cache_trajet(conn, cle):
    row = conn.execute("SELECT minutes, source FROM trajets_cache WHERE cle = ?", (cle,)).fetchone()
    return (row["minutes"], row["source"]) if row else None


def _memoriser_trajet(conn, cle, minutes, source):
    conn.execute("INSERT OR REPLACE INTO trajets_cache(cle, minutes, source, date) VALUES (?,?,?,?)",
                 (cle, minutes, source, maintenant()))
    conn.commit()


def trajet_voiture(conn, lat, lon, p):
    """Durée en voiture (minutes, déjà majorée pour le trafic) + source du calcul."""
    dest = (p["travail_lat"], p["travail_lon"])
    cle = f"voiture|{lat:.4f}|{lon:.4f}|{dest[0]:.4f}|{dest[1]:.4f}"
    majoration = 1 + p["majoration_trafic_pct"] / 100

    cache = _cache_trajet(conn, cle)
    if cache and cache[1] == "OpenRouteService":
        return round(cache[0] * majoration), cache[1]

    if os.getenv("ORS_API_KEY"):
        try:
            # Adresse officielle depuis 2026 (api.openrouteservice.org est en cours d'abandon)
            for essai in range(3):
                r = requests.post(
                    "https://api.heigit.org/openrouteservice/v2/directions/driving-car",
                    json={"coordinates": [[lon, lat], [dest[1], dest[0]]]},
                    headers={"Authorization": os.getenv("ORS_API_KEY"), "User-Agent": AGENT},
                    timeout=30)
                if r.status_code != 429:      # 429 = trop de demandes par minute : on patiente
                    break
                time.sleep(20)
            r.raise_for_status()
            minutes = r.json()["routes"][0]["summary"]["duration"] / 60
            _memoriser_trajet(conn, cle, minutes, "OpenRouteService")
            return round(minutes * majoration), "OpenRouteService"
        except (requests.RequestException, KeyError, IndexError) as e:
            print(f"[geo] échec trajet voiture ORS: {e}")

    # Estimation sans service : distance x 1,35 (détours) à 55 km/h de moyenne
    km = distance_km(lat, lon, *dest) * 1.35
    return round(km / 55 * 60 * majoration), "estimation"


def _duree_iso(texte):
    """'PT1H5M' -> 65 (minutes)."""
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", texte or "")
    if not m:
        return None
    j, h, mi = (int(x or 0) for x in m.groups())
    return j * 1440 + h * 60 + mi


def _prochain_mardi():
    """Un jour de semaine "normal" pour calculer les horaires de transport."""
    d = datetime.now() + timedelta(days=1)
    while d.weekday() != 1:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def trajet_transports(conn, lat, lon, p):
    """Durée en transports en commun (minutes) via mobiliteit.lu, ou (None, raison)."""
    cle_api = os.getenv("MOBILITEIT_API_KEY")
    if not cle_api:
        return None, "pas de clé mobiliteit.lu"
    dest = (p["travail_lat"], p["travail_lon"])
    cle = f"tc|{lat:.4f}|{lon:.4f}|{dest[0]:.4f}|{dest[1]:.4f}|{p['heure_arrivee']}"
    cache = _cache_trajet(conn, cle)
    if cache:
        return cache

    try:
        r = requests.get(
            "https://cdt.hafas.de/opendata/apiserver/trip",
            params={"accessId": cle_api, "format": "json", "lang": "fr",
                    "originCoordLat": lat, "originCoordLong": lon,
                    "destCoordLat": dest[0], "destCoordLong": dest[1],
                    "date": _prochain_mardi(), "time": p["heure_arrivee"],
                    "searchForArrival": 1, "numF": 3},
            headers={"User-Agent": AGENT}, timeout=30)
        r.raise_for_status()
        trajets = r.json().get("Trip") or []
        durees = [_duree_iso(t.get("duration")) for t in trajets]
        durees = [d for d in durees if d]
        if not durees:
            return None, "aucun trajet trouvé"
        minutes = min(durees)
        _memoriser_trajet(conn, cle, minutes, "mobiliteit.lu")
        return minutes, "mobiliteit.lu"
    except (requests.RequestException, ValueError) as e:
        print(f"[geo] échec trajet transports: {e}")
        return None, "erreur mobiliteit.lu"
