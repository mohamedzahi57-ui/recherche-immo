"""Tests automatiques (lancer avec : python -m pytest)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from immo import boite_mail, extraction, frais, geo, parametres, score  # noqa: E402

EXEMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exemples")
P = dict(parametres.DEFAUTS)


def test_frais_luxembourg_avec_bellegen_akt():
    f = frais.calculer_frais(450000, "LU", 0, P)
    # droits 27 000 + transcription 4 500 + notaire 4 500 - crédit 31 500 (plafonné aux droits) = 4 500
    assert f["frais_total"] == 4500
    assert f["cout_total"] == 454500


def test_frais_luxembourg_credit_plafonne_au_montant_par_acheteur():
    f = frais.calculer_frais(800000, "LU", 0, P)
    # droits 48 000 + 8 000 + notaire 8 000 - 40 000 = 24 000
    assert f["frais_total"] == 24000


def test_frais_france_et_belgique():
    assert frais.calculer_frais(300000, "FR", 0, P)["frais_total"] == 24000
    assert frais.calculer_frais(300000, "FR", 1, P)["frais_total"] == 9000
    assert frais.calculer_frais(300000, "BE", 0, P)["frais_total"] == 18000


def test_extraction_athome():
    with open(os.path.join(EXEMPLES, "demo_athome.eml"), "rb") as fh:
        m = boite_mail.depuis_rfc822(fh.read(), "fichier")
    annonces = extraction.extraire_annonces(m)
    assert len(annonces) == 3
    a = annonces[0]
    assert a["source"] == "atHome" and a["id_externe"] == "90000001"
    assert a["prix"] == 465000 and a["surface"] == 78 and a["chambres"] == 2
    assert a["commune"] == "Bertrange" and a["pays"] == "LU"
    assert a["type_bien"] == "appartement" and annonces[1]["type_bien"] == "maison"
    assert a["garage"] == 1 and a["terrasse"] == 1 and a["rez_de_chaussee"] == 1
    assert annonces[1]["plain_pied"] == 1 and annonces[1]["travaux"] == 1
    assert annonces[2]["commune"] == "Esch-sur-Alzette"


def test_extraction_lignes_separees_wortimmo():
    with open(os.path.join(EXEMPLES, "demo_wortimmo.eml"), "rb") as fh:
        m = boite_mail.depuis_rfc822(fh.read(), "fichier")
    annonces = {a["id_externe"]: a for a in extraction.extraire_annonces(m)}
    assert annonces["70000001"]["prix"] == 289000
    assert annonces["70000001"]["pays"] == "FR"
    assert annonces["70000002"]["commune"] == "Arlon" and annonces["70000002"]["pays"] == "BE"


def test_frontiere():
    assert geo.distance_frontiere_km(49.6116, 6.1319) == 0  # Luxembourg-Ville
    assert geo.distance_frontiere_km(49.4794, 5.9806) < 5  # Audun-le-Tiche
    assert geo.distance_frontiere_km(49.3579, 6.1683) > 5  # Thionville


def test_criteres_et_score():
    b = {"prix": 520000, "pays": "LU", "chambres": 2, "type_bien": "appartement", "surface": 80}
    assert any("prix" in r for r in score.verifier_criteres(b, P))
    b["prix"] = 450000
    assert score.verifier_criteres(b, P) == []
    s_sans, _ = score.calculer_score(b, P)
    b["garage"] = 1
    s_avec, _ = score.calculer_score(b, P)
    assert s_avec > s_sans


def test_athome_lien_mandrill_et_format_reel():
    """Format réel des alertes atHome : liens de suivi Mandrill, surface 'm 2', commune en fin de ligne."""
    import base64, json
    from immo import extraction

    def lien(url):
        interne = json.dumps({"url": url})
        p = base64.urlsafe_b64encode(json.dumps({"p": interne}).encode()).decode()
        return "https://mandrillapp.com/track/click/1/www.athome.lu?p=" + p

    html = (
        f'<table><tr><td><a href="{lien("https://www.athome.lu/id-9448980.html")}">'
        f'296 000 € Maison - 3 chambres - 120 m <sup>2</sup> Errouville</a>'
        f'<a href="{lien("https://www.athome.lu/agence/159447")}">Agence</a></td></tr>'
        f'<tr><td><a href="{lien("https://www.athome.lu/id-9449033.html")}">'
        f'198 500 € Appartement - 1 chambre - 55 m <sup>2</sup> Trier</a></td></tr></table>'
    )
    an = extraction.extraire_annonces({"html": html, "text": "", "subject": "alerte"})
    par_id = {a["id_externe"]: a for a in an}
    assert set(par_id) == {"9448980", "9449033"}          # le lien d'agence est ignoré
    a = par_id["9448980"]
    assert (a["prix"], a["surface"], a["chambres"], a["type_bien"]) == (296000, 120, 3, "maison")
    assert (a["commune"], a["pays"]) == ("Errouville", "FR")
    assert par_id["9449033"]["commune"] == "Trier"         # commune inconnue gardée, pays trouvé plus tard


def test_immotop_liens_chiffres():
    """Alerte Immotop réelle : liens chiffrés clicks.immotop.lu, annonce reconnue par son titre."""
    from immo import extraction
    lien = "https://clicks.immotop.lu/f/a/abc~~/AAAHahA~/xyz"
    html = (f'<table><tr><td><a href="{lien}">﻿Appartement 2 chambres 87, Route d\'Arlon, Strassen﻿</a>'
            f'<p>€ 1 198 000</p><p>82 m&sup2; | 2 chambres/pièces</p><a href="{lien}">VOIR LES DÉTAILS</a></td></tr>'
            '<tr><td><a href="https://clicks.immotop.lu/f/a/autre">Gérer la recherche</a></td></tr></table>')
    res = extraction.extraire_annonces({"html": html, "text": ""})
    assert len(res) == 1
    a = res[0]
    assert a["source"] == "Immotop" and a["id_externe"].startswith("t-")
    assert a["prix"] == 1198000 and a["surface"] == 82 and a["chambres"] == 2
    assert a["commune"] == "Strassen" and a["type_bien"] == "appartement"


def test_terrain_et_prefabrique():
    from immo import extraction, parametres, score
    t = extraction.analyser_texte("Terrain à bâtir 6,5 ares Bettembourg 245 000 €")
    assert t["type_bien"] == "terrain" and t["surface"] == 650
    m = extraction.analyser_texte("Maison préfabriquée ossature bois 110 m² Dudelange 420 000 €")
    assert m["prefabrique"] == 1 and m["type_bien"] == "maison"
    p = dict(parametres.DEFAUTS)
    assert score.verifier_criteres(dict(t, pays="LU"), p) == []
    assert score.verifier_criteres(dict(t, pays="LU", prix=300000), p)


def test_seloger_vignettes():
    from immo import extraction
    html = ("<table><tr><td><a href='https://click.by.seloger.com/?qs=a1'>361&#8239;000&nbsp;€</a>"
            "<a href='https://click.by.seloger.com/?qs=a2'>Maison à vendre</a>"
            "<a href='https://click.by.seloger.com/?qs=a3'>4 pièces · 147 m²</a>"
            "<a href='https://click.by.seloger.com/?qs=a4'>Volmerange-les-Mines (57330)</a>"
            "<a href='https://click.by.seloger.com/?qs=a5'>Voir l'annonce</a></td></tr>"
            "<tr><td><a href='https://click.by.seloger.com/?qs=b1'>99 000 €</a> Terrain constructible "
            "Audun-le-Tiche (57390) <a href='https://click.by.seloger.com/?qs=b2'>Voir l'annonce</a></td></tr></table>")
    a = extraction.extraire_annonces({"html": html, "text": "", "subject": "seloger.com"})
    assert len(a) == 2
    m = [x for x in a if x["type_bien"] == "maison"][0]
    assert m["prix"] == 361000 and m["surface"] == 147 and m["chambres"] == 3 and m["pays"] == "FR"
    assert [x for x in a if x["type_bien"] == "terrain"][0]["prix"] == 99000


def test_ajout_manuel(monkeypatch):
    from immo import extraction, importeur
    a = extraction.annonce_manuelle("Maison plain-pied 3 ch 120 m2 Perl 420.000 EUR",
                                    "https://www.athome.lu/vente/maison/perl/id-7654321.html")
    assert (a["source"], a["id_externe"]) == ("atHome", "7654321")
    assert a["prix"] == 420000 and a["surface"] == 120 and a["commune"] == "Perl"
    b = extraction.annonce_manuelle("Terrain 5 ares Bettembourg 240 000 €")
    assert b["source"] == "Ajout manuel" and b["type_bien"] == "terrain"
    monkeypatch.setenv("IMAP_USER", "moi@example.com")
    assert importeur.est_ajout_par_email({"subject": "Fwd: belle maison #immo", "from": "Moi <moi@example.com>"})
    assert not importeur.est_ajout_par_email({"subject": "#immo", "from": "autre@example.com"})


def test_quartiers_luxembourg():
    from immo import quartiers
    assert quartiers.trouver("Studio 1 chambre à vendre à Luxembourg-Rollingergrund 490 000 €") == "Rollingergrund"
    assert quartiers.trouver("€ 494 000 Appartement, Gasperich-Cloche d'or, Luxembourg") == "Gasperich / Cloche d'Or"
    assert quartiers.trouver("Appartement à vendre à Luxembourg-Limpertsberg") == "Limpertsberg"
    assert quartiers.trouver("Studio à vendre, Gare, Luxembourg") == "Gare"
    assert quartiers.trouver("Maison à Bertrange, proche de la gare de Luxembourg") is None
    assert quartiers.est_luxembourg_ville("Luxembourg") and not quartiers.est_luxembourg_ville("Esch-sur-Alzette")


def test_annonces_retirees(monkeypatch, tmp_path):
    from immo import db, retraits
    monkeypatch.setattr(db, "CHEMIN_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(db, "DOSSIER_DATA", str(tmp_path))
    db.initialiser()
    conn = db.connecter()
    for i in (1, 2, 3):
        conn.execute("INSERT INTO biens(id, titre, demo) VALUES (?, 'b', 0)", (i,))
    conn.executemany("INSERT INTO annonces(bien_id, source, url, id_externe) VALUES (?,?,?,?)", [
        (1, "atHome", "https://www.athome.lu/vente/maison/x/id-111.html", "111"),   # disparue
        (2, "atHome", "https://www.athome.lu/id-222.html", "222"),                  # disparue...
        (2, "atHome", "https://www.athome.lu/id-333.html", "333"),                  # ...mais doublon encore en ligne
        (3, "Immotop", "https://www.immotop.lu/annonces/1/", "1"),                  # non vérifiable
    ])
    conn.commit()
    reponses = {"111": "retiree", "222": "retiree", "333": "en_ligne"}
    monkeypatch.setattr(retraits, "etat_annonce",
                        lambda url, s=None: (reponses[url.split("id-")[1].split(".")[0]], 0))
    bilan = retraits.verifier(conn, pause=0)
    assert bilan["verifiees"] == 3 and bilan["biens_retires"] == 1
    statuts = dict(conn.execute("SELECT id, statut FROM biens").fetchall())
    assert statuts == {1: "retiré", 2: "nouveau", 3: "nouveau"}
    conn.close()


def test_commune_avant_nom_agence():
    from immo import communes
    t = communes.trouver_commune
    assert t("Maison 3 chambres à vendre à Ettelbruck 1 111 € 241 m² Engel & Völkers LUXEMBOURG")[0] == "Ettelbruck"
    assert t("Maison 5 chambres à vendre à Wiltz 295 000 € L'AGENCE Real Estate Bereldange")[0] == "Wiltz"
    assert t("Maison individuelle rue de Longwy 98, Niederkorn, Differdange")[0] == "Differdange"
    assert t("Studio à vendre, Belval-Université, Esch-sur-Alzette")[0] == "Esch-sur-Alzette"
    assert t("programme neuf à Esch-sur-Alzette*** Nouveau projet à Belval")[0] == "Esch-sur-Alzette"
    assert t("Studio à vendre à Luxembourg-Gare")[0] == "Luxembourg"


def test_localite_suivie_de_sa_commune():
    from immo import communes
    t = communes.trouver_commune
    assert t("Appartement deuxième étage, Bascharage, Käerjeng") == ("Käerjeng", "LU")
    assert t("Maison 128 Rte de Longwy, Rodange, Pétange")[0] == "Pétange"
    assert t("Maison 7, Rue Principale, Haut-Martelange, Wolwelange, Rambrouch") == ("Rambrouch", "LU")
    assert t("Appartement 1 chambre Belval Esch-sur-Alzette, Luxembourg, Belval-Université")[0] == "Esch-sur-Alzette"


def test_communes_composees():
    from immo import communes
    t = communes.trouver_commune
    assert t("Terrain constructible, Lannen, Redange/Attert") == ("Redange", "LU")
    assert t("Maison 383 m², Osweiler, Rosport-Mompach") == ("Rosport-Mompach", "LU")
    assert t("Appartement 5,Rue Jean-Jacques Rousseau, Belval Sud-Lycée, Sanem")[0] == "Sanem"
    assert t("Terrain non constructible, Septfontaines, Simmerschmelz, Habscht")[0] == "Habscht"
    assert t("programme neuf à Steinfort À Hagen, au 14-16 A Rue Neuve") == ("Steinfort", "LU")


def test_noms_de_rue():
    from immo import communes
    t = communes.trouver_commune
    assert t("Appartement 1 chambre 23 michele rodange, Gare, Luxembourg")[0] == "Luxembourg"
    assert t("Appartement 2 chambres 87, Route d'Arlon, Strassen")[0] == "Strassen"
    assert t("Appartement rez-de-chaussée, Schifflange")[0] == "Schifflange"
    assert t("Appartement 2 chambres neuf, rez-de-chaussée, Nocher, Nocher-Route, Goesdorf")[0] == "Goesdorf"
    assert t("400 000 € Appartement - 1 chambre - 52 m 2 Belval")[0] == "Esch-sur-Alzette"


def test_retrait_par_email_et_annonces_anciennes(monkeypatch, tmp_path):
    from immo import db, retraits
    monkeypatch.setattr(db, "CHEMIN_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(db, "DOSSIER_DATA", str(tmp_path))
    monkeypatch.setenv("IMAP_USER", "moi@example.com")
    db.initialiser()
    conn = db.connecter()
    conn.execute("INSERT INTO biens(id, titre, demo) VALUES (1, 'b', 0), (2, 'c', 0)")
    conn.execute("INSERT INTO annonces(bien_id, source, url, id_externe, date_reception) VALUES "
                 "(1, 'Immotop', '', 'abc123', '2026-01-01 10:00'), "
                 "(2, 'SeLoger', 'https://www.seloger.com/annonce/achat/x/ABCDEFGH12', 'ABCDEFGH12', '2026-01-01')")
    conn.commit()
    corps = retraits.corps_email_retrait(conn, 1)
    assert "annonce: Immotop|abc123" in corps
    assert retraits.est_email_retrait({"subject": "#retire annonce retirée", "from": "Moi <moi@example.com>"})
    assert not retraits.est_email_retrait({"subject": "#retire", "from": "autre@example.com"})
    assert retraits.appliquer_email_retrait(conn, corps + "\nhttps://www.seloger.com/annonce/achat/x/ABCDEFGH12") == 2
    assert {r[0] for r in conn.execute("SELECT statut FROM biens")} == {"retiré"}
    conn.close()


def test_badge_ancienne_annonce():
    import app
    b = {"derniere_vue": "2026-01-01 10:00", "confirme": 0, "statut": "nouveau"}
    assert app.est_ancienne(b, "2026-03-01")
    assert not app.est_ancienne(dict(b, confirme=1), "2026-03-01")      # vu en ligne sur atHome
    assert not app.est_ancienne(b, "2025-12-01")                         # pas encore 60 jours
    assert not app.est_ancienne(b, None)                                 # réglage à 0 = désactivé


def test_lot_collecte_par_email(monkeypatch, tmp_path):
    import json
    from immo import db, importeur
    monkeypatch.setattr(db, "CHEMIN_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(db, "DOSSIER_DATA", str(tmp_path))
    monkeypatch.setenv("IMAP_USER", "moi@example.com")
    monkeypatch.setattr(importeur, "enrichir_bien", lambda *a, **k: None, raising=False)
    db.initialiser()
    conn = db.connecter()
    lot = {"annonces": [{"url": "https://www.leboncoin.fr/ad/ventes_immobilieres/3314253566",
                         "texte": "Zoufftgen 57330 · Maison 5 pièces 120 m² · 350000 €"}]}
    m = {"id": "x", "subject": "#collecte Leboncoin", "from": "Moi <moi@example.com>", "date": "",
         "text": "Lot\n" + json.dumps(lot), "origine": "imap"}
    assert importeur.est_collecte_par_email(m) and not importeur.est_ajout_par_email(m)
    assert importeur.importer_collecte_email(conn, m["text"], dict(P)) == 1
    assert conn.execute("SELECT source FROM annonces").fetchone()[0] == "Leboncoin"
    conn.close()
