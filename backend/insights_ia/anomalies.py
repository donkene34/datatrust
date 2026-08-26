"""
anomalies.py — Détection d'anomalies multivariées via Isolation Forest sur
la matrice_features de l'artefact analytique.

Complète les outliers par colonne du Milestone #1 (IQR, une colonne à la
fois) par une détection qui capture des combinaisons anormales sur
plusieurs colonnes ensemble (ADR-1, ADR-4 du Milestone #1).

random_state fixé (RANDOM_STATE) pour garantir la reproductibilité
(ADR-1, correction #3 V2.1) : deux exécutions sur le même dataset
produisent exactement les mêmes scores (critère d'acceptation 11).
"""

import time

from sklearn.ensemble import IsolationForest

RANDOM_STATE = 42
CONTAMINATION_PAR_DEFAUT = "auto"


def detecter(artefact, contamination=CONTAMINATION_PAR_DEFAUT):
    """
    Détecte les anomalies multivariées dans la matrice_features de
    l'artefact analytique (construit par artefact_analytique.construire()).

    Retourne la liste COMPLÈTE des anomalies détectées (ADR-9 : pas de
    troncature ici — c'est invite.py, à l'étape suivante, qui décide quoi
    résumer pour le LLM) :
    {
        "methode": "isolation_forest",
        "parametres": {"contamination": ..., "random_state": int},
        "colonnes_utilisees": [str, ...],
        "nombre_observations_analysees": int,
        "nombre_anomalies_detectees": int,
        "taux_anomalies": float,
        "anomalies": [
            {"indice_observation": int, "score": float, "colonnes": [str, ...]},
            ...
        ],
        "temps_execution_secondes": float,
    }

    Un score plus négatif signifie une anomalie plus marquée
    (decision_function de scikit-learn). "colonnes" liste les colonnes
    numériques utilisées par le modèle — la même liste pour chaque
    anomalie, car Isolation Forest est entraîné une fois sur l'ensemble
    des colonnes retenues, pas colonne par colonne.

    Avec contamination="auto" (valeur par défaut, décision DILANE — voir
    ADR-9), le taux d'anomalies détectées n'est PAS calibré pour viser un
    pourcentage précis : il peut être élevé (ex. 36 % sur un dataset RH) sans
    que cela signifie que les données sont mauvaises. C'est pour cette
    raison que "methode" et "parametres" sont inclus dans la sortie : le
    LLM (via invite.py) doit toujours savoir comment le résultat a été
    obtenu avant de l'interpréter.

    Si aucune colonne numérique n'est exploitable (artefact vide), retourne
    une structure vide plutôt que de lever une exception : un dataset sans
    colonne numérique (ex. entièrement catégoriel) reste un cas valide.
    """
    colonnes_utilisees = artefact["colonnes_numeriques"]
    matrice = artefact["matrice_features"]
    parametres = {"contamination": contamination, "random_state": RANDOM_STATE}

    debut = time.perf_counter()

    if not colonnes_utilisees or matrice.shape[0] == 0:
        return {
            "methode": "isolation_forest",
            "parametres": parametres,
            "colonnes_utilisees": colonnes_utilisees,
            "nombre_observations_analysees": int(matrice.shape[0]) if matrice.size else 0,
            "nombre_anomalies_detectees": 0,
            "taux_anomalies": 0.0,
            "anomalies": [],
            "temps_execution_secondes": round(time.perf_counter() - debut, 4),
        }

    modele = IsolationForest(random_state=RANDOM_STATE, contamination=contamination)
    modele.fit(matrice)

    predictions = modele.predict(matrice)  # -1 = anomalie, 1 = normal
    scores = modele.decision_function(matrice)  # plus négatif = plus anormal

    anomalies = [
        {
            "indice_observation": int(indice),
            "score": round(float(score), 4),
            "colonnes": colonnes_utilisees,
        }
        for indice, (prediction, score) in enumerate(zip(predictions, scores))
        if prediction == -1
    ]

    nombre_observations = int(matrice.shape[0])
    taux_anomalies = round(len(anomalies) / nombre_observations, 4) if nombre_observations else 0.0

    return {
        "methode": "isolation_forest",
        "parametres": parametres,
        "colonnes_utilisees": colonnes_utilisees,
        "nombre_observations_analysees": nombre_observations,
        "nombre_anomalies_detectees": len(anomalies),
        "taux_anomalies": taux_anomalies,
        "anomalies": anomalies,
        "temps_execution_secondes": round(time.perf_counter() - debut, 4),
    }
