"""rapport.py — Assemble le rapport JSON final : score global + détail par dimension + profil."""

import os

from .dimensions.completude import calculer_completude
from .dimensions.coherence import calculer_coherence
from .dimensions.fraicheur import calculer_fraicheur
from .dimensions.aberrations import calculer_aberrations
from .dimensions.unicite import calculer_unicite
from .dimensions.validite import calculer_validite
from .chargeur import charger_csv
from .profileur import profiler_jeu_de_donnees
from .notation import calculer_score_global


def generer_rapport(chemin_fichier, ponderations=None, date_reference=None):
    nom_jeu_donnees = os.path.basename(chemin_fichier)
    tableau, separateur = charger_csv(chemin_fichier)
    profil = profiler_jeu_de_donnees(tableau, nom_jeu_donnees)

    scores_dimensions = {
        "completude": calculer_completude(tableau, profil),
        "coherence": calculer_coherence(tableau, profil),
        "unicite": calculer_unicite(tableau, profil),
        "validite": calculer_validite(tableau, profil),
        "aberrations": calculer_aberrations(tableau, profil),
        "fraicheur": calculer_fraicheur(tableau, profil, date_reference=date_reference),
    }

    score_global = calculer_score_global(scores_dimensions, ponderations)

    return {
        "jeu_de_donnees": nom_jeu_donnees,
        "separateur_detecte": separateur,
        "score_global": score_global,
        "scores_dimensions": scores_dimensions,
        "profil": profil,
    }
