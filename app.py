"""Application web de recherche immobilière (Luxembourg + frontière FR/BE).

Lancement : double-cliquer sur lancer.bat (ou `python app.py`), puis ouvrir
http://localhost:5000 sur l'ordinateur, ou http://<adresse-du-PC>:5000 sur le
téléphone connecté au même Wi-Fi (l'adresse s'affiche au démarrage).
"""
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for

load_dotenv()  # lit le fichier .env (clés et mots de passe)

from immo import boite_mail, constructeurs, db, frais, importeur, parametres, retraits, score  # noqa: E402

app = Flask(__name__)
app.jinja_env.globals["constructeurs"] = constructeurs
app.secret_key = os.getenv("FLASK_SECRET", "cle-locale-" + str(os.getpid()))
DOSSIER_DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exemples")

TRIS = {
    "score": "score", "prix": "prix", "prix_m2": "prix_m2", "surface": "surface", "chambres": "chambres",
    "voiture": "trajet_voiture_min", "transports": "trajet_tc_min", "cout": "cout_total",
    "date": "date_ajout", "commune": "commune",
}
CHAMPS_EDITABLES = ["titre", "prix", "surface", "commune", "code_postal", "pays", "type_bien", "etage",
                    "chambres", "garage", "parking", "terrasse", "neuf", "travaux", "plain_pied", "prefabrique",
                    "rez_de_chaussee", "trajet_tc_min"]
CHAMPS_NUMERIQUES = {"prix", "surface", "chambres", "garage", "parking", "terrasse", "neuf", "travaux",
                     "plain_pied", "rez_de_chaussee", "trajet_tc_min", "prefabrique"}


# ---------------------------------------------------------------- protection par mot de passe
def protege(vue):
    """Si APP_PASSWORD est défini dans .env, le navigateur demande identifiant 'immo' + ce mot de passe."""
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        mdp = os.getenv("APP_PASSWORD")
        if mdp:
            auth = request.authorization
            if not auth or auth.username != "immo" or auth.password != mdp:
                return Response("Accès protégé", 401, {"WWW-Authenticate": 'Basic realm="Recherche immo"'})
        return vue(*args, **kwargs)
    return enveloppe


# ---------------------------------------------------------------- application téléphone (PWA)
# Ces deux fichiers permettent d'« installer » le site sur le téléphone comme une application.
# Ils sont servis à la racine du site pour que l'application couvre toutes les pages.
@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest"), 200, {"Content-Type": "application/manifest+json"}


@app.route("/sw.js")
def service_worker():
    rep = app.send_static_file("sw.js")
    rep.headers["Cache-Control"] = "no-cache"
    return rep


@app.template_filter("euros")
def euros(v):
    return "—" if v is None else f"{v:,.0f} €".replace(",", " ")


@app.template_filter("minutes")
def minutes(v):
    return "—" if v is None else f"{v:.0f} min"


@app.template_filter("oui_non")
def oui_non(v):
    return {1: "oui", 0: "non"}.get(v, "?")


# ---------------------------------------------------------------- annonces anciennes
# derniere_vue : dernière fois qu'une alerte a montré le bien ; confirme : vu en ligne par la vérification atHome
SQL_ANCIENNETE = ("(SELECT max(date_reception) FROM annonces a WHERE a.bien_id = b.id) derniere_vue, "
                  "(SELECT count(*) FROM annonces a WHERE a.bien_id = b.id AND COALESCE(a.retiree, 0) != 1 "
                  "AND a.verifie_le IS NOT NULL) confirme")


def seuil_ancien(p):
    """Date (AAAA-MM-JJ) avant laquelle un bien non confirmé est « ancienne annonce » (None = désactivé)."""
    jours = p.get("jours_annonce_ancienne") or 0
    return (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d") if jours > 0 else None


@app.template_test("ancienne")
def est_ancienne(b, seuil):
    return bool(seuil and b["derniere_vue"] and b["derniere_vue"][:10] < seuil and not b["confirme"]
                and b["statut"] != "retiré")


# ---------------------------------------------------------------- pages
@app.route("/")
@protege
def liste():
    f = request.args
    conditions, valeurs = [], []
    if not f.get("tous") and not app.jinja_env.globals.get("statique"):
        conditions.append("(hors_criteres IS NULL OR hors_criteres = '')")
    if not f.get("retires"):  # annonces disparues des sites (voir immo/retraits.py)
        conditions.append("COALESCE(statut, '') != 'retiré'")
    with db.connecter() as conn:
        seuil = seuil_ancien(parametres.lire(conn))
    if seuil and not f.get("anciennes") and not app.jinja_env.globals.get("statique"):
        # vu seulement par une alerte de plus de N jours, jamais confirmé en ligne (Immotop, SeLoger)
        conditions.append(
            "NOT (substr((SELECT max(date_reception) FROM annonces a WHERE a.bien_id = b.id), 1, 10) < ? "
            "AND NOT EXISTS (SELECT 1 FROM annonces a WHERE a.bien_id = b.id AND COALESCE(a.retiree, 0) != 1 "
            "AND a.verifie_le IS NOT NULL))")
        valeurs.append(seuil)
    if f.get("pays"):
        conditions.append("pays = ?")
        valeurs.append(f["pays"])
    if f.get("commune"):
        conditions.append("(lower(commune) LIKE ? OR lower(COALESCE(quartier, '')) LIKE ?)")
        valeurs += [f"%{f['commune'].lower()}%"] * 2
    for champ, op, cle in (("prix", "<=", "prix_max"), ("prix", ">=", "prix_min"), ("surface", ">=", "surface_min"),
                           ("chambres", ">=", "chambres_min"), ("prix_m2", "<=", "prix_m2_max"),
                           ("score", ">=", "score_min"), ("surface", "<=", "surface_max"),
                           ("trajet_voiture_min", "<=", "voiture_max"), ("trajet_tc_min", "<=", "tc_max")):
        if f.get(cle):
            try:
                valeurs.append(float(f[cle]))
                conditions.append(f"{champ} {op} ?")
            except ValueError:
                pass
    if f.get("garage") == "garage":
        conditions.append("garage = 1")
    elif f.get("garage") == "garage_ou_parking":
        conditions.append("(garage = 1 OR parking = 1)")
    if f.get("type") == "prefab":  # maison préfabriquée, ou terrain pour en poser une
        conditions.append("(type_bien = 'terrain' OR prefabrique = 1)")
    elif f.get("type"):
        conditions.append("type_bien = ?")
        valeurs.append(f["type"])

    tri = TRIS.get(f.get("tri", "score"), "score")
    ordre = "ASC" if f.get("ordre") == "asc" else "DESC"
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with db.connecter() as conn:
        biens = conn.execute(
            f"SELECT b.*, (SELECT group_concat(source, ', ') FROM annonces a WHERE a.bien_id = b.id) sources, "
            f"(SELECT url FROM annonces a WHERE a.bien_id = b.id LIMIT 1) url, {SQL_ANCIENNETE} "
            f"FROM biens b {where} ORDER BY {tri} IS NULL, {tri} {ordre}, score DESC", valeurs).fetchall()
        nb_total = conn.execute("SELECT count(*) n FROM biens WHERE COALESCE(statut, '') != 'retiré'").fetchone()["n"]
        p = parametres.lire(conn)
    return render_template("liste.html", biens=biens, f=f, tri=f.get("tri", "score"), ordre=ordre.lower(),
                           nb_total=nb_total, p=p, seuil_ancien=seuil_ancien(p))


@app.route("/bien/<int:bien_id>", methods=["GET", "POST"])
@protege
def fiche(bien_id):
    with db.connecter() as conn:
        p = parametres.lire(conn)
        if request.method == "POST":
            ancien = conn.execute("SELECT * FROM biens WHERE id = ?", (bien_id,)).fetchone()
            maj = {}
            for c in CHAMPS_EDITABLES:
                if c not in request.form:
                    continue
                v = request.form[c].strip()
                if c in CHAMPS_NUMERIQUES:
                    v = float(v.replace(",", ".").replace(" ", "")) if v not in ("", "?") else None
                    if v is not None and c not in ("prix", "surface", "trajet_tc_min"):
                        v = int(v)
                else:
                    v = v or None
                maj[c] = v
            modifies = {c for c in maj if maj[c] != ancien[c]}
            if "trajet_tc_min" in modifies:
                maj["trajet_tc_source"] = "manuel" if maj["trajet_tc_min"] is not None else None
            if "commune" in modifies or "code_postal" in modifies:
                maj.update(lat=None, lon=None)  # on relocalisera le bien
            deja = set(filter(None, (ancien["champs_modifies"] or "").split(",")))
            maj["champs_modifies"] = ",".join(sorted(deja | modifies))
            maj["date_maj"] = db.maintenant()
            conn.execute(f"UPDATE biens SET {', '.join(k + ' = ?' for k in maj)} WHERE id = ?",
                         (*maj.values(), bien_id))
            conn.commit()
            importeur.enrichir_bien(conn, bien_id, p, avec_reseau=bool({"commune", "code_postal"} & modifies))
            flash("Fiche enregistrée et recalculée.")
            return redirect(url_for("fiche", bien_id=bien_id))

        b = conn.execute(f"SELECT b.*, {SQL_ANCIENNETE} FROM biens b WHERE id = ?", (bien_id,)).fetchone()
        if not b:
            return "Bien introuvable", 404
        annonces = conn.execute("SELECT * FROM annonces WHERE bien_id = ? ORDER BY id", (bien_id,)).fetchall()
        corps_retrait = retraits.corps_email_retrait(conn, bien_id)
    detail_frais = frais.calculer_frais(b["prix"], b["pays"], b["neuf"], p)
    note, detail_score = score.calculer_score(dict(b), p)
    return render_template("fiche.html", b=b, annonces=annonces, frais=detail_frais, detail_score=detail_score,
                           p=p, budget=p["prix_max"], seuil_ancien=seuil_ancien(p),
                           corps_retrait=corps_retrait, moi=os.getenv("IMAP_USER", ""))


@app.route("/bien/<int:bien_id>/retirer", methods=["POST"])
@protege
def retirer(bien_id):
    """Vous avez constaté que l'annonce n'existe plus (ex. Immotop, SeLoger) : le bien quitte la liste."""
    with db.connecter() as conn:
        conn.execute("UPDATE biens SET statut = 'retiré', date_retrait = ? WHERE id = ?",
                     (db.maintenant()[:10], bien_id))
        conn.commit()
        corps = retraits.corps_email_retrait(conn, bien_id)
    try:  # la version en ligne a sa propre base : on la prévient par un e-mail à vous-même
        boite_mail.envoyer_a_soi(f"{retraits.MOT_CLE_RETRAIT} annonce retirée", corps)
        flash("Bien retiré de la liste. Le téléphone sera mis à jour au prochain passage de la routine "
              "(moins de 2 h).")
    except Exception as e:
        flash(f"Bien retiré de la liste du PC, mais l'e-mail pour le téléphone n'a pas pu partir ({e}).")
    return redirect(url_for("fiche", bien_id=bien_id))


@app.route("/bien/<int:bien_id>/remettre", methods=["POST"])
@protege
def remettre(bien_id):
    """Remet dans la liste un bien marqué « retiré » par erreur (et ne le revérifie plus)."""
    with db.connecter() as conn:
        conn.execute("UPDATE biens SET statut = 'nouveau', date_retrait = NULL WHERE id = ?", (bien_id,))
        conn.execute("UPDATE annonces SET retiree = -1 WHERE bien_id = ?", (bien_id,))  # -1 = ne plus vérifier
        conn.commit()
    flash("Le bien est de nouveau dans la liste.")
    return redirect(url_for("fiche", bien_id=bien_id))


@app.route("/ajouter", methods=["GET", "POST"])
@protege
def ajouter():
    """Ajout à la main d'une annonce vue sur un site (texte et/ou lien collés)."""
    if request.method == "POST":
        texte = request.form.get("texte", "")
        url = request.form.get("url", "")
        if not (texte.strip() or url.strip()):
            flash("Collez au moins le texte ou le lien de l'annonce.")
            return redirect(url_for("ajouter"))
        with db.connecter() as conn:
            p = parametres.lire(conn)
            res, bien_id = importeur.ajouter_manuellement(conn, texte, url, p)
        flash({"nouveau": "Bien ajouté. Vérifiez et complétez la fiche si besoin.",
               "doublon": "Ce bien était déjà dans la liste (même commune, prix et surface) : fiche complétée.",
               "deja_vu": "Cette annonce est déjà dans la liste."}[res])
        return redirect(url_for("fiche", bien_id=bien_id)) if bien_id else redirect(url_for("ajouter"))
    return render_template("ajouter.html")


@app.route("/parametres", methods=["GET", "POST"])
@protege
def page_parametres():
    with db.connecter() as conn:
        if request.method == "POST":
            if request.form.get("action") == "geocoder_travail":
                p = parametres.lire(conn)
                parametres.ecrire(conn, {"travail_adresse": request.form.get("travail_adresse",
                                                                               p["travail_adresse"])})
                importeur.assurer_coordonnees_travail(conn, parametres.lire(conn), forcer=True)
                conn.execute("DELETE FROM trajets_cache")
                conn.execute("UPDATE biens SET trajet_voiture_min = NULL, trajet_tc_min = NULL "
                             "WHERE trajet_tc_source IS NULL OR trajet_tc_source != 'manuel'")
                conn.commit()
                flash("Adresse du travail relocalisée. Les trajets seront recalculés au prochain import.")
            else:
                parametres.ecrire(conn, parametres.depuis_formulaire(request.form))
                importeur.recalculer_tout(conn)
                flash("Paramètres enregistrés, tous les biens ont été recalculés.")
            return redirect(url_for("page_parametres"))
        p = parametres.lire(conn)
    return render_template("parametres.html", p=p, sections=parametres.sections())


@app.route("/import")
@protege
def page_import():
    with db.connecter() as conn:
        journal = conn.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 40").fetchall()
        emails = conn.execute("SELECT * FROM emails_traites ORDER BY date_traitement DESC LIMIT 30").fetchall()
        nb_demo = conn.execute("SELECT count(*) n FROM biens WHERE demo = 1").fetchone()["n"]
    etat = {
        "graph_configure": boite_mail.graph_configure(),
        "graph_compte": boite_mail.compte_graph() if boite_mail.graph_configure() else None,
        "imap_configure": boite_mail.imap_configure(),
        "ors": bool(os.getenv("ORS_API_KEY")),
        "mobiliteit": bool(os.getenv("MOBILITEIT_API_KEY")),
        "dossier_eml": boite_mail.DOSSIER_EML,
    }
    return render_template("import.html", journal=journal, emails=emails, etat=etat, nb_demo=nb_demo,
                           connexion=boite_mail.etat_connexion_graph())


@app.post("/import/lancer")
@protege
def lancer_import():
    try:
        flash(importeur.importer())
    except Exception as e:
        flash(f"Erreur : {e}")
    return redirect(url_for("page_import"))


@app.post("/import/demo")
@protege
def import_demo():
    flash(importeur.importer(demo_dossier=DOSSIER_DEMO))
    return redirect(url_for("liste"))


@app.post("/import/supprimer-demo")
@protege
def supprimer_demo():
    importeur.supprimer_demo()
    flash("Données de démonstration supprimées.")
    return redirect(url_for("page_import"))


@app.post("/outlook/connecter")
@protege
def connecter_outlook():
    try:
        boite_mail.demarrer_connexion_graph()
    except Exception as e:
        flash(f"Connexion Outlook impossible : {e}")
    return redirect(url_for("page_import"))


@app.get("/outlook/etat")
@protege
def etat_outlook():
    return jsonify(boite_mail.etat_connexion_graph())


# ---------------------------------------------------------------- import automatique
def boucle_import_auto():
    """Tâche de fond : importe les e-mails toutes les N heures tant que l'application tourne."""
    time.sleep(20)
    p = parametres.DEFAUTS
    while True:
        try:
            with db.connecter() as conn:
                p = parametres.lire(conn)
            if p["import_auto"] and (boite_mail.graph_configure() or boite_mail.imap_configure()):
                importeur.importer()
        except Exception as e:
            print(f"[import auto] {e}")
        time.sleep(max(1, p.get("import_intervalle_heures", 4)) * 3600)


def adresse_locale():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "adresse-du-PC"


if __name__ == "__main__":
    db.initialiser()
    threading.Thread(target=boucle_import_auto, daemon=True).start()
    port = int(os.getenv("PORT", "5000"))
    print("\n" + "=" * 60)
    print(f"  Application lancée.  Sur ce PC : http://localhost:{port}")
    print(f"  Sur le téléphone (même Wi-Fi) : http://{adresse_locale()}:{port}")
    print("  Pour arrêter : fermer cette fenêtre (ou Ctrl+C).")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
