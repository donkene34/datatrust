"""
profileur.py — Produit le contrat de données structuré consommé par les
dimensions et, en Phase 2, par l'AI Insights Engine.

Sortie (contrat entièrement en français) :
{
  "jeu_de_donnees": str,
  "taille": {"lignes": int, "colonnes": int},
  "colonnes": [
      {"nom", "type", "nb_manquants", "taux_manquants", "nb_valeurs_uniques",
       "min", "max", "moyenne", "ecart_type"}
  ],
  "correlations": [{"colonne_a", "colonne_b", "coefficient"}]
}
"""

import numpy as np
import pandas as pd

from .utilitaires_type import type_lisible


def _profil_colonne(serie):
    non_nuls = serie.dropna()
    nb_manquants = int(serie.isna().sum())
    total = len(serie)
    taux_manquants = round(nb_manquants / total, 4) if total else 0.0

    infos = {
        "nom": serie.name,
        "type": type_lisible(serie),
        "nb_manquants": nb_manquants,
        "taux_manquants": taux_manquants,
        "nb_valeurs_uniques": int(non_nuls.nunique()),
        "min": None,
        "max": None,
        "moyenne": None,
        "ecart_type": None,
    }

    if pd.api.types.is_numeric_dtype(serie) and len(non_nuls) > 0:
        finies = non_nuls[np.isfinite(non_nuls.astype(float))] if len(non_nuls) else non_nuls
        if len(finies) > 0:
            infos["min"] = float(finies.min())
            infos["max"] = float(finies.max())
            infos["moyenne"] = round(float(finies.mean()), 4)
            infos["ecart_type"] = round(float(finies.std()), 4) if len(finies) > 1 else 0.0

    return infos


def _calculer_correlations(tableau):
    colonnes_numeriques = tableau.select_dtypes(include=[np.number]).columns
    if len(colonnes_numeriques) < 2:
        return []

    matrice_correlation = tableau[colonnes_numeriques].corr(method="pearson")
    paires = []
    vues = set()
    for colonne_a in colonnes_numeriques:
        for colonne_b in colonnes_numeriques:
            if colonne_a == colonne_b:
                continue
            cle = tuple(sorted([colonne_a, colonne_b]))
            if cle in vues:
                continue
            vues.add(cle)
            coefficient = matrice_correlation.loc[colonne_a, colonne_b]
            if pd.notna(coefficient):
                paires.append({
                    "colonne_a": cle[0],
                    "colonne_b": cle[1],
                    "coefficient": round(float(coefficient), 4),
                })
    return paires


def profiler_jeu_de_donnees(tableau, nom_jeu_donnees):
    profil_colonnes = [_profil_colonne(tableau[col]) for col in tableau.columns]

    return {
        "jeu_de_donnees": nom_jeu_donnees,
        "taille": {"lignes": int(tableau.shape[0]), "colonnes": int(tableau.shape[1])},
        "colonnes": profil_colonnes,
        "correlations": _calculer_correlations(tableau),
    }
