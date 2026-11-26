"""Base de données locale SQLite.

Tout est stocké dans un seul fichier : data/immo.db
(on peut le sauvegarder simplement en copiant ce fichier).
"""
import os
import sqlite3
from datetime import datetime

DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DATA = os.path.join(DOSSIER_RACINE, "data")
CHEMIN_DB = os.path.join(DOSSIER_DATA, "immo.db")

SCHEMA = """
-- Un "bien" = un logement réel. Il peut être vu dans plusieurs annonces (doublons).
CREATE TABLE IF NOT EXISTS biens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT,
    prix REAL,
    surface REAL,
    prix_m2 REAL,
    commune TEXT,
    code_postal TEXT,
    pays TEXT,                 -- 'LU', 'FR', 'BE' ou NULL si inconnu
    type_bien TEXT,            -- 'maison', 'appartement', 'terrain', 'autre'
    etage TEXT,
    chambres INTEGER,
    garage INTEGER,            -- 1 oui / 0 non / NULL inconnu
    parking INTEGER,
    terrasse INTEGER,
    neuf INTEGER,
    travaux INTEGER,
    plain_pied INTEGER,
    rez_de_chaussee INTEGER,
    prefabrique INTEGER,       -- maison préfabriquée / modulaire / ossature bois
    description TEXT,
    lat REAL,
    lon REAL,
    distance_frontiere_km REAL,
    trajet_voiture_min REAL,
    trajet_voiture_source TEXT,
    trajet_tc_min REAL,
    trajet_tc_source TEXT,
    frais_total REAL,
    cout_total REAL,
    score REAL,
    hors_criteres TEXT,        -- raisons séparées par ' | ' (vide = dans les critères)
    statut TEXT DEFAULT 'nouveau',
    favori INTEGER DEFAULT 0,
    notes TEXT,
    champs_modifies TEXT DEFAULT '',  -- champs corrigés à la main (protégés)
    demo INTEGER DEFAULT 0,
    date_ajout TEXT,
    date_maj TEXT
);

-- Une "annonce" = une apparition d'un bien sur un site (atHome, Immotop...).
CREATE TABLE IF NOT EXISTS annonces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bien_id INTEGER REFERENCES biens(id) ON DELETE CASCADE,
    source TEXT,
    url TEXT,
    id_externe TEXT,
    email_id TEXT,
    texte_brut TEXT,
    date_reception TEXT,
    UNIQUE(source, id_externe)
);

-- E-mails déjà lus (pour ne jamais les traiter deux fois).
CREATE TABLE IF NOT EXISTS emails_traites (
    message_id TEXT PRIMARY KEY,
    sujet TEXT,
    expediteur TEXT,
    date_reception TEXT,
    nb_annonces INTEGER,
    origine TEXT,
    date_traitement TEXT
);

-- Mémoire des adresses déjà géolocalisées (évite de redemander aux services).
CREATE TABLE IF NOT EXISTS geocache (
    requete TEXT PRIMARY KEY,
    lat REAL,
    lon REAL,
    pays TEXT,
    date TEXT
);

-- Mémoire des temps de trajet déjà calculés.
CREATE TABLE IF NOT EXISTS trajets_cache (
    cle TEXT PRIMARY KEY,
    minutes REAL,
    source TEXT,
    date TEXT
);

-- Paramètres modifiables depuis la page "Paramètres".
CREATE TABLE IF NOT EXISTS parametres (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

-- Journal des opérations (imports, erreurs...).
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    niveau TEXT,
    message TEXT
);
"""


def connecter():
    """Ouvre une connexion à la base (une par requête / par tâche)."""
    os.makedirs(DOSSIER_DATA, exist_ok=True)
    conn = sqlite3.connect(CHEMIN_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialiser():
    """Crée les tables si elles n'existent pas encore."""
    with connecter() as conn:
        conn.executescript(SCHEMA)
        # colonnes ajoutées après coup (bases existantes)
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(biens)")}
        if "prefabrique" not in colonnes:
            conn.execute("ALTER TABLE biens ADD COLUMN prefabrique INTEGER")


def maintenant():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def journaliser(conn, message, niveau="info"):
    """Ajoute une ligne dans le journal (visible sur la page Import)."""
    conn.execute(
        "INSERT INTO journal(date, niveau, message) VALUES (?,?,?)",
        (maintenant(), niveau, message),
    )
    conn.commit()
    print(f"[{niveau}] {message}")
