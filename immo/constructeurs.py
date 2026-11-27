"""Constructeurs de maisons préfabriquées / ossature bois, affichés avec le filtre
« Maison préfabriquée / terrain ».

Sélection faite le 27/11/2026 à partir de sources publiques :
  - notes « marque » : comparatif fertig-haus.net (avis clients agrégés, 2026) ;
  - notes « agence » : avis Google Maps de l'agence ou de la maison témoin la plus proche ;
  - prix : sites des constructeurs et comparatifs (fertig-haus.net, fertighaus.de, architecteo.com).
Les prix sont indicatifs (hors terrain, souvent hors fondations/raccordements) : demandez un devis.
Pour mettre à jour la liste, modifiez simplement ce fichier.
"""

DATE_SELECTION = "27/11/2026"

REPERES = [
    "Luxembourg : clé en main ≈ 2 900 – 3 800 €/m² habitable (fertig-haus.net, 2026), plus dalle ou cave "
    "(35 000 – 90 000 €) et raccordements (8 000 – 15 000 €).",
    "France : maison ossature bois clé en main ≈ 1 300 – 2 200 €/m² (moyenne nationale, architecteo.com) ; "
    "« hors d'eau hors d'air » ≈ 800 – 1 000 €/m².",
    "Avec votre budget (terrain ≤ 250 000 €, total ≤ 500 000 €), il reste environ 250 000 € pour la maison : "
    "≈ 70 – 85 m² clé en main au Luxembourg, davantage côté France ou avec un constructeur polonais.",
]

CONSTRUCTEURS = [
    # ------------------------------------------------------------------ Luxembourg
    {"pays": "LU", "nom": "Naturhome", "ville": "Troisvierges",
     "note": "4,2/5 (11 avis Google)",
     "description": "Constructeur luxembourgeois de maisons contemporaines en ossature bois, conçues et "
                    "fabriquées dans son propre atelier, souvent en standard passif.",
     "offre": "Maisons individuelles sur mesure, clé en main.",
     "tarif": "Sur devis (repère Luxembourg : 2 900 – 3 800 €/m²).",
     "tel": "+352 97 81 71", "email": "info@naturhome.lu", "site": "https://www.naturhome.lu/"},
    {"pays": "LU", "nom": "EHS – Eco Home Systems", "ville": "Weiswampach",
     "note": "5/5 (1 seul avis Google)",
     "description": "Ossature bois et bois massif : la structure est fabriquée dans ses ateliers puis montée "
                    "sur place. Basse énergie et passif.",
     "offre": "Maisons neuves, extensions, surélévations ; structure seule ou clé en main.",
     "tarif": "Sur devis.",
     "tel": "+352 26 90 89 54", "email": "info@ehs.lu", "site": "https://www.ehs.lu/"},
    {"pays": "LU", "nom": "Hamboislux", "ville": "Weiswampach",
     "note": "pas encore d'avis Google",
     "description": "Charpentier-constructeur bois avec centre de taille numérique : maisons ossature bois "
                    "et CLT (bois massif contrecollé), basse énergie, passives ou zéro énergie.",
     "offre": "Maisons sur plan d'architecte, clé en main possible.",
     "tarif": "Sur devis.",
     "tel": "+352 661 414 541", "email": "", "site": "https://www.hamboislux.eu/"},
    # ------------------------------------------------------------------ Allemagne
    {"pays": "DE", "nom": "SchwörerHaus", "ville": "Maison témoin à Trierweiler (près de Trèves)",
     "note": "4,8/5 (1 842 avis, marque)",
     "description": "Grand fabricant allemand de maisons préfabriquées en bois (bois de ses propres forêts "
                    "et scierie). Page dédiée au Luxembourg ; plusieurs bungalows de plain-pied.",
     "offre": "Maisons clé en main, bungalows, maisons à étage.",
     "tarif": "À partir d'environ 2 700 €/m² (fertig-haus.net).",
     "tel": "+49 651 69985821", "email": "", "site": "https://www.schwoererhaus.de/de-lu/"},
    {"pays": "DE", "nom": "Bien-Zenker", "ville": "Info-Center Trèves (Paulinstraße 75)",
     "note": "4,7/5 (1 423 avis, marque) ; agence de Trèves 5/5 (3 avis)",
     "description": "Fabricant allemand depuis 1906, élu « Unternehmen des Jahres 2025 » (Deutschland Test). "
                    "Large gamme de bungalows.",
     "offre": "Bungalows et maisons clé en main, prix fixe.",
     "tarif": "À partir d'environ 2 300 €/m² ; bungalow Ambience 77 (77 m²) dès 293 553 € clé en main.",
     "tel": "+49 651 99153144", "email": "", "site": "https://www.bien-zenker.de/haeuser/bungalow.html"},
    {"pays": "DE", "nom": "FingerHaus", "ville": "Maison témoin région Trèves (Hetzerath)",
     "note": "4,6/5 (1 124 avis, marque) ; agence 5/5 (17 avis)",
     "description": "Fabricant allemand primé pour son service (DISQ/ntv 2024, Focus Money). "
                    "97 % de clients prêts à le recommander selon son enquête.",
     "offre": "Bungalows NIVO de plain-pied, maisons clé en main ou à finir soi-même.",
     "tarif": "2 448 – 3 019 €/m² ; bungalow NIVO 80 (81 m²) dès 265 651 € clé en main.",
     "tel": "+49 171 1904918", "email": "", "site": "https://www.fingerhaus.de/haeuser/bungalows/nivo/"},
    {"pays": "DE", "nom": "WeberHaus", "ville": "Bauforum Luxembourg, 148 route d'Arlon, Strassen",
     "note": "4,7/5 (1 689 avis, marque) ; bureau de Strassen 2,2/5 (5 avis Google)",
     "description": "Fabricant allemand haut de gamme qui construit aussi au Luxembourg et en France, avec un "
                    "bureau à Strassen (rendez-vous par téléphone).",
     "offre": "Maisons sur mesure clé en main, accompagnement terrain et financement.",
     "tarif": "À partir d'environ 3 300 €/m² (plutôt haut de gamme).",
     "tel": "+352 26 31 06 33", "email": "luxembourg@weberhaus.com",
     "site": "https://www.weberhaus.de/erleben/bauforen/luxembourg/"},
    # ------------------------------------------------------------------ France (Lorraine)
    {"pays": "FR", "nom": "Filao Bois", "ville": "Montenach (57), près de Sierck-les-Bains",
     "note": "5/5 (16 avis Google)",
     "description": "Constructeur de maisons en bois et charpentier, à une dizaine de km de la frontière "
                    "luxembourgeoise.",
     "offre": "Maisons ossature bois, charpente, terrasses.",
     "tarif": "Sur devis (repère France : 1 300 – 2 200 €/m² clé en main).",
     "tel": "+33 7 84 42 94 64", "email": "", "site": "https://www.filao-bois.fr/"},
    {"pays": "FR", "nom": "Les Maisons Cocoon", "ville": "Creutzwald (57)",
     "note": "5/5 (11 avis Google)",
     "description": "Constructeur mosellan de maisons en bois.",
     "offre": "Maisons individuelles ossature bois.",
     "tarif": "Sur devis.",
     "tel": "+33 7 69 57 64 70", "email": "", "site": "https://www.lesmaisonscocoon.fr/"},
    {"pays": "FR", "nom": "ABC Lange Création", "ville": "Faulquemont (57)",
     "note": "4,9/5 (13 avis Google)",
     "description": "Atelier de menuiserie spécialisé dans la maison passive en Grand Est.",
     "offre": "Maisons passives bois.",
     "tarif": "Sur devis.",
     "tel": "+33 3 87 81 93 22", "email": "", "site": "https://www.maison-passive-grand-est.fr/"},
    {"pays": "FR", "nom": "Maisons booa", "ville": "Marly (57), près de Metz",
     "note": "5/5 (5 avis Google)",
     "description": "Réseau de constructeurs de maisons à ossature bois préfabriquée (murs fabriqués en "
                    "usine), agence près de Metz.",
     "offre": "Maisons bois sur catalogue ou sur mesure.",
     "tarif": "Sur devis.",
     "tel": "+33 3 68 31 98 32", "email": "", "site": "https://www.booa.fr/agence/marly/"},
    {"pays": "FR", "nom": "Ambiance Bois Concept", "ville": "Ars-sur-Moselle (57)",
     "note": "4,5/5 (26 avis Google)",
     "description": "Constructeur de maisons en bois, charpente, isolation et solaire.",
     "offre": "Maisons ossature bois, extensions, terrasses.",
     "tarif": "Sur devis.",
     "tel": "+33 6 47 34 88 50", "email": "", "site": "http://www.ambiance-bois-concept.fr/"},
    # ------------------------------------------------------------------ Pologne
    {"pays": "PL", "nom": "Danwood", "ville": "Usine à Bielsko-Biała ; filiale allemande",
     "note": "4,3/5 (1 067 avis, marque)",
     "description": "Grand fabricant polonais de maisons à ossature bois, très présent en Allemagne et "
                    "actif au Luxembourg. Plus de 200 plans, maisons basse consommation avec pompe à chaleur.",
     "offre": "Maisons et bungalows clé en main, prix garanti jusqu'à 18 mois.",
     "tarif": "À partir d'environ 1 900 €/m² ; bungalow Family 96 dès 187 200 € (prix Allemagne).",
     "tel": "", "email": "", "site": "https://www.danwood.de/"},
    {"pays": "PL", "nom": "FirstHome.pl", "ville": "Pologne",
     "note": "pas de note publique trouvée",
     "description": "Constructeur polonais de maisons préfabriquées à ossature bois, prix serrés. "
                    "Livraison hors de Pologne à confirmer avec eux.",
     "offre": "Maisons préfabriquées, plusieurs niveaux de finition.",
     "tarif": "À partir de 135 000 PLN (≈ 31 000 €, probablement hors finitions).",
     "tel": "+48 508 108 060", "email": "biuro@firsthome.pl", "site": "https://www.firsthome.pl/en/"},
]

NOMS_PAYS = {"FR": "France (Lorraine)", "LU": "Luxembourg", "DE": "Allemagne", "PL": "Pologne"}
