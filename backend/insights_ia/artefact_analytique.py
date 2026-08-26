"""
artefact_analytique.py — Construit l'artefact analytique interne : la matrice
de features numériques utilisée par anomalies.py (Isolation Forest) et
visualisations.py (histogrammes, heatmap de corrélations).

Cet artefact est un objet interne au pipeline Milestone #2 : il n'est jamais
sérialisé tel quel dans le JSON de sortie, et n'est jamais transmis au LLM
(voir ADR-3 de claude/milestone_2_intelligence.md). Seuls des résultats déjà
agrégés (scores d'anomalie, statistiques descriptives) en sont dérivés avant
d'atteindre le prompt.

Règle de construction (ADR-6) : seules les colonnes numériques avec un taux
de valeurs manquantes <= 50 % sont retenues ; les valeurs manquantes
restantes sont imputées par la médiane de la colonne, car Isolation Forest
ne gère pas nativement les NaN. Les colonnes exclues et la méthode
d'imputation sont documentées dans metadonnees_transformation.
"""

import time

import numpy as np

from qualite_donnees.chargeur import charger_csv

SEUIL_TAUX_MANQUANTS_MAX = 0.5


def _selectionner_colonnes_numeriques(tableau):
    """
    Sépare les colonnes numériques du tableau en deux groupes : celles
    retenues (taux de manquants <= seuil) et celles exclues, avec leur
    raison d'exclusion.
    """
    colonnes_retenues = []
    colonnes_exclues = []

    colonnes_numeriques = tableau.select_dtypes(include=[np.number]).columns

    for nom_colonne in colonnes_numeriques:
        serie = tableau[nom_colonne]
        taux_manquants = float(serie.isna().mean()) if len(serie) else 0.0

        if taux_manquants > SEUIL_TAUX_MANQUANTS_MAX:
            colonnes_exclues.append({
                "nom": nom_colonne,
                "raison": f"taux_manquants={round(taux_manquants, 4)} > seuil {SEUIL_TAUX_MANQUANTS_MAX}",
            })
        else:
            colonnes_retenues.append(nom_colonne)

    return colonnes_retenues, colonnes_exclues


def _imputer_par_mediane(tableau, colonnes_retenues):
    """
    Retourne (matrice_features, colonnes_imputees) : la sous-table des
    colonnes retenues avec les valeurs manquantes remplacées par la médiane
    de chaque colonne, convertie en tableau numpy prêt pour Isolation Forest.

    Les valeurs infinies (+inf/-inf) sont d'abord traitées comme manquantes :
    Isolation Forest ne les gère pas nativement non plus, et ADR-6 ne les
    mentionne pas explicitement — point ajouté ici par prudence technique,
    à signaler comme précision d'implémentation plutôt que comme changement
    d'architecture.
    """
    sous_tableau = tableau[colonnes_retenues].copy()
    sous_tableau = sous_tableau.replace([np.inf, -np.inf], np.nan)
    colonnes_imputees = []

    for nom_colonne in colonnes_retenues:
        nb_manquants = int(sous_tableau[nom_colonne].isna().sum())
        if nb_manquants > 0:
            mediane = sous_tableau[nom_colonne].median()
            sous_tableau[nom_colonne] = sous_tableau[nom_colonne].fillna(mediane)
            colonnes_imputees.append(nom_colonne)

    matrice_features = sous_tableau.to_numpy(dtype=float)
    return matrice_features, colonnes_imputees


def construire(chemin_fichier, identifiant_dataset=None):
    """
    Construit l'ArtefactAnalytique à partir du chemin du fichier CSV.

    Recharge le CSV via le même loader que le Milestone #1
    (qualite_donnees.chargeur.charger_csv), donc la même détection de
    séparateur / valeurs manquantes. C'est un second chargement du fichier,
    léger surcoût jugé acceptable pour le MVP (voir milestone_2_intelligence.md).

    Retourne un dict :
    {
        "identifiant_dataset": str,
        "nombre_observations": int,
        "colonnes_numeriques": [str, ...],
        "colonnes_exclues": [{"nom": str, "raison": str}, ...],
        "matrice_features": np.ndarray,
        "metadonnees_transformation": {
            "imputation": "mediane",
            "colonnes_imputees": [str, ...],
        },
        "temps_secondes": {"chargement": float, "transformation": float},
    }

    "temps_secondes" existe pour le critère d'acceptation 12 (mesure réelle
    des performances sur le dataset énergie) : distingue le temps de lecture
    du CSV du temps de sélection/imputation des colonnes, sans ajouter un
    troisième chargement du fichier juste pour chronométrer.
    """
    debut_chargement = time.perf_counter()
    tableau, _separateur = charger_csv(chemin_fichier)
    temps_chargement = time.perf_counter() - debut_chargement

    if identifiant_dataset is None:
        identifiant_dataset = chemin_fichier

    debut_transformation = time.perf_counter()
    colonnes_retenues, colonnes_exclues = _selectionner_colonnes_numeriques(tableau)
    matrice_features, colonnes_imputees = _imputer_par_mediane(tableau, colonnes_retenues)
    temps_transformation = time.perf_counter() - debut_transformation

    return {
        "identifiant_dataset": identifiant_dataset,
        "nombre_observations": int(tableau.shape[0]),
        "colonnes_numeriques": colonnes_retenues,
        "colonnes_exclues": colonnes_exclues,
        "matrice_features": matrice_features,
        "metadonnees_transformation": {
            "imputation": "mediane",
            "colonnes_imputees": colonnes_imputees,
        },
        "temps_secondes": {
            "chargement": round(temps_chargement, 4),
            "transformation": round(temps_transformation, 4),
        },
    }
