"""
visualisations.py — Génère les graphiques du rapport (Matplotlib), encodés
en base64, à partir de l'artefact analytique (Milestone #2) et du profil
structuré (Milestone #1, profileur.py).

ADR-2 : les images sont intégrées au JSON final pour que le frontend
(Phase 4) puisse les afficher sans recalcul, mais elles ne sont JAMAIS
transmises au LLM (notre LLM, Groq, est un modèle texte, pas vision) —
seul le résumé statistique retourné dans "resume_pour_prompt" est fourni
au LLM, via invite.py.
"""

import base64
import io

import matplotlib
matplotlib.use("Agg")  # pas d'affichage interactif : environnement serveur
import matplotlib.pyplot as plt
import numpy as np


def _encoder_figure_base64(figure):
    tampon = io.BytesIO()
    figure.savefig(tampon, format="png", bbox_inches="tight")
    plt.close(figure)
    tampon.seek(0)
    return base64.b64encode(tampon.read()).decode("ascii")


def _choisir_colonne_histogramme(artefact, profil):
    """
    Choisit, parmi les colonnes numériques retenues par l'artefact
    analytique, celle avec le plus grand coefficient de variation
    (écart-type / moyenne) — jugée la plus "intéressante" à visualiser.
    À défaut d'information suffisante, retourne la première colonne retenue.
    """
    colonnes_retenues = artefact["colonnes_numeriques"]
    if not colonnes_retenues:
        return None

    profils_colonnes = {c["nom"]: c for c in profil.get("colonnes", [])}

    meilleure_colonne = colonnes_retenues[0]
    meilleur_cv = -1
    for nom in colonnes_retenues:
        info = profils_colonnes.get(nom)
        if not info or not info.get("moyenne"):
            continue
        moyenne = info["moyenne"]
        ecart_type = info.get("ecart_type") or 0.0
        if moyenne == 0:
            continue
        coefficient_variation = abs(ecart_type / moyenne)
        if coefficient_variation > meilleur_cv:
            meilleur_cv = coefficient_variation
            meilleure_colonne = nom

    return meilleure_colonne


def generer_histogramme(artefact, profil):
    """
    Génère un histogramme (PNG encodé en base64) de la colonne numérique
    jugée la plus pertinente. Retourne (image_base64, statistiques) —
    (None, None) si aucune colonne numérique n'est disponible.
    """
    colonne = _choisir_colonne_histogramme(artefact, profil)
    if colonne is None:
        return None, None

    colonnes_retenues = artefact["colonnes_numeriques"]
    indice_colonne = colonnes_retenues.index(colonne)
    valeurs = artefact["matrice_features"][:, indice_colonne]

    figure, axe = plt.subplots(figsize=(6, 4))
    nb_bacs = min(30, max(5, int(np.sqrt(len(valeurs)))))
    axe.hist(valeurs, bins=nb_bacs, color="#4C72B0")
    axe.set_title(f"Distribution — {colonne}")
    axe.set_xlabel(colonne)
    axe.set_ylabel("Fréquence")

    image_base64 = _encoder_figure_base64(figure)

    statistiques = {
        "colonne": colonne,
        "nombre_observations": int(len(valeurs)),
        "min": round(float(valeurs.min()), 4),
        "max": round(float(valeurs.max()), 4),
        "nombre_bacs": nb_bacs,
    }

    return image_base64, statistiques


def generer_heatmap_correlations(profil):
    """
    Génère une heatmap (PNG encodé en base64) de la matrice de corrélations
    du profil Milestone #1. Retourne (image_base64, statistiques) —
    (None, None) si aucune corrélation disponible (moins de 2 colonnes
    numériques dans le dataset).
    """
    correlations = profil.get("correlations", [])
    if not correlations:
        return None, None

    colonnes = sorted({c["colonne_a"] for c in correlations} | {c["colonne_b"] for c in correlations})
    index_colonne = {nom: i for i, nom in enumerate(colonnes)}
    n = len(colonnes)
    matrice = np.eye(n)

    for paire in correlations:
        i = index_colonne[paire["colonne_a"]]
        j = index_colonne[paire["colonne_b"]]
        matrice[i, j] = paire["coefficient"]
        matrice[j, i] = paire["coefficient"]

    figure, axe = plt.subplots(figsize=(max(4, n * 0.5), max(4, n * 0.5)))
    image = axe.imshow(matrice, cmap="coolwarm", vmin=-1, vmax=1)
    axe.set_xticks(range(n))
    axe.set_yticks(range(n))
    axe.set_xticklabels(colonnes, rotation=90, fontsize=6)
    axe.set_yticklabels(colonnes, fontsize=6)
    axe.set_title("Corrélations entre colonnes numériques")
    figure.colorbar(image, ax=axe, fraction=0.046, pad=0.04)

    image_base64 = _encoder_figure_base64(figure)

    correlation_max = max(correlations, key=lambda c: abs(c["coefficient"]))

    statistiques = {
        "nombre_colonnes": n,
        "nombre_paires": len(correlations),
        "correlation_la_plus_forte": {
            "colonne_a": correlation_max["colonne_a"],
            "colonne_b": correlation_max["colonne_b"],
            "coefficient": correlation_max["coefficient"],
        },
    }

    return image_base64, statistiques


def generer(artefact, profil):
    """
    Génère l'ensemble des visualisations du rapport à partir de l'artefact
    analytique (histogramme) et du profil Milestone #1 (heatmap de
    corrélations).

    Retourne :
    {
        "images": {
            "histogramme": "<base64 PNG>" | None,
            "heatmap_correlations": "<base64 PNG>" | None,
        },
        "resume_pour_prompt": {   # jamais transmis avec les images — voir invite.py / ADR-3
            "histogramme": {...} | None,
            "heatmap_correlations": {...} | None,
        },
    }
    """
    image_histogramme, stats_histogramme = generer_histogramme(artefact, profil)
    image_heatmap, stats_heatmap = generer_heatmap_correlations(profil)

    return {
        "images": {
            "histogramme": image_histogramme,
            "heatmap_correlations": image_heatmap,
        },
        "resume_pour_prompt": {
            "histogramme": stats_histogramme,
            "heatmap_correlations": stats_heatmap,
        },
    }
