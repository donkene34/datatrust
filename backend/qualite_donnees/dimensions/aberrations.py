"""Dimension : anomalies / valeurs aberrantes — détection statistique via IQR (ADR-4)."""


def calculer_aberrations(tableau, profil):
    colonnes_numeriques = [
        c["nom"] for c in profil["colonnes"]
        if tableau[c["nom"]].dtype.kind in "ifc"
    ]

    if not colonnes_numeriques:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Aucune colonne numérique disponible pour détecter des valeurs aberrantes.",
            "details": {},
        }

    total_valeurs = 0
    total_aberrations = 0
    problemes = []

    for colonne in colonnes_numeriques:
        serie = tableau[colonne].dropna()
        if len(serie) < 4:
            continue

        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue

        borne_basse = q1 - 1.5 * iqr
        borne_haute = q3 + 1.5 * iqr
        aberrations = serie[(serie < borne_basse) | (serie > borne_haute)]

        total_valeurs += len(serie)
        total_aberrations += len(aberrations)

        if len(aberrations) > 0:
            taux = len(aberrations) / len(serie)
            problemes.append(f"{colonne}: {len(aberrations)} valeur(s) atypique(s) détectée(s) ({taux * 100:.1f}%)")

    if total_valeurs == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Colonnes numériques insuffisantes (trop peu de valeurs ou variance nulle) pour détecter des aberrations.",
            "details": {},
        }

    taux = total_aberrations / total_valeurs
    score = round(max(0.0, 100 - taux * 100), 2)
    explication = "; ".join(problemes[:3]) if problemes else "Aucune valeur aberrante détectée (méthode IQR)."

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {"nb_aberrations": total_aberrations, "problemes": problemes},
    }
