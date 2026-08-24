"""notation.py — Agrégation pondérée des 6 dimensions en un score global (ADR-2)."""

PONDERATIONS_PAR_DEFAUT = {
    "completude": 1 / 6,
    "coherence": 1 / 6,
    "unicite": 1 / 6,
    "validite": 1 / 6,
    "aberrations": 1 / 6,
    "fraicheur": 1 / 6,
}


def calculer_score_global(scores_dimensions, ponderations=None):
    ponderations = ponderations or PONDERATIONS_PAR_DEFAUT
    applicables = {dim: p for dim, p in ponderations.items() if dim in scores_dimensions}
    poids_total = sum(applicables.values())

    if poids_total == 0:
        return 0.0

    somme_ponderee = sum(scores_dimensions[dim]["score"] * p for dim, p in applicables.items())
    return round(somme_ponderee / poids_total, 2)
