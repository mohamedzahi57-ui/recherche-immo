"""Calcul des frais d'acquisition et du coût total.

Luxembourg :
    droits d'enregistrement (~6 %) + transcription (~1 %) + notaire (~1 %)
    - crédit d'impôt "Bëllegen Akt" (résidence principale), plafonné :
      * au montant par acheteur x nombre d'acheteurs,
      * et aux droits d'enregistrement + transcription (il ne peut pas les dépasser).
    Remarque : pour un bien neuf vendu sur plan (VEFA), les droits ne portent en
    réalité que sur la quote-part du terrain ; le calcul ici est donc prudent.
France / Belgique :
    un pourcentage global paramétrable (sans Bëllegen Akt).
"""


def calculer_frais(prix, pays, neuf, p):
    """Retourne {'lignes': [(libellé, montant)], 'frais_total', 'cout_total', 'remarque'}
    ou None si le prix est inconnu."""
    if not prix:
        return None

    lignes = []
    remarque = ""

    if pays in ("FR",):
        pct = p["fr_frais_neuf_pct"] if neuf else p["fr_frais_ancien_pct"]
        etat = "neuf" if neuf else "ancien"
        lignes.append((f"Frais d'acquisition France ({etat}, {pct:g} %)", prix * pct / 100))
    elif pays in ("BE",):
        pct = p["be_frais_pct"]
        lignes.append((f"Frais d'acquisition Belgique ({pct:g} %)", prix * pct / 100))
    else:
        # Luxembourg (ou pays inconnu : on applique le barème luxembourgeois par prudence)
        if pays != "LU":
            remarque = "Pays inconnu : barème luxembourgeois appliqué par défaut."
        droits = prix * p["lu_droits_enregistrement_pct"] / 100
        transcription = prix * p["lu_transcription_pct"] / 100
        notaire = prix * p["lu_notaire_pct"] / 100
        lignes.append((f"Droits d'enregistrement ({p['lu_droits_enregistrement_pct']:g} %)", droits))
        lignes.append((f"Droits de transcription ({p['lu_transcription_pct']:g} %)", transcription))
        lignes.append((f"Notaire ({p['lu_notaire_pct']:g} %)", notaire))
        if p["lu_residence_principale"]:
            plafond = p["lu_bellegen_akt_par_acheteur"] * max(1, p["lu_nb_acheteurs"])
            credit = min(droits + transcription, plafond)
            lignes.append((f"Crédit d'impôt Bëllegen Akt ({p['lu_nb_acheteurs']} acheteur(s))", -credit))

    frais_total = sum(m for _, m in lignes)
    return {
        "lignes": lignes,
        "frais_total": round(frais_total),
        "cout_total": round(prix + frais_total),
        "remarque": remarque,
    }
