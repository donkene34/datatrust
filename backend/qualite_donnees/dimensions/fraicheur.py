"""
Dimension : fraîcheur — voir Milestone #1 V2, ADR-3 (point d'arbitrage #2).

Si aucune colonne temporelle n'est détectée, retourne explicitement
{"score": 100, "statut": "non_applicable"} plutôt qu'un score identique à un
vrai résultat évalué, pour éviter qu'un jeu de données sans dimension
temporelle n'apparaisse à tort comme "excellent en fraîcheur".
"""

import re

import pandas as pd

MOTIFS_DATE = [
    r"^\d{4}-\d{2}-\d{2}",
    r"^\d{2}/\d{2}/\d{4}",
    r"^\d{2}-\d{2}-\d{4}",
]

INDICES_NOM = ["date", "time", "timestamp", "year", "created", "updated"]

AGE_MAX_JOURS_POUR_SCORE_ZERO = 1095  # 3 ans


def _detecter_colonnes_date(tableau, profil):
    """
    Deux niveaux de confiance :
    - candidats_motif : le contenu de la colonne ressemble directement à des
      dates (regex) — confiance haute, retenu en priorité.
    - candidats_indice_nom : le NOM de la colonne évoque une date ("date",
      "time", ...) mais son contenu ne matche pas le motif — on ne le retient
      QUE si un échantillon parse effectivement en date (>70% de succès), pour
      éviter les faux positifs comme "OverTime" (Oui/Non) qui contient "time"
      en sous-chaîne sans être une colonne temporelle.
    """
    candidats_motif = []
    candidats_indice_nom = []

    for infos_colonne in profil["colonnes"]:
        colonne = infos_colonne["nom"]
        echantillon = tableau[colonne].dropna().astype(str).head(50).tolist()
        if not echantillon:
            continue

        correspondances = sum(any(re.match(p, v.strip()) for p in MOTIFS_DATE) for v in echantillon)
        indice_motif = (correspondances / len(echantillon)) > 0.5

        if indice_motif:
            candidats_motif.append(colonne)
            continue

        indice_nom = any(k in colonne.lower() for k in INDICES_NOM)
        if indice_nom:
            echantillon_analyse = pd.to_datetime(pd.Series(echantillon), errors="coerce", format="mixed")
            taux_succes = echantillon_analyse.notna().sum() / len(echantillon)
            if taux_succes > 0.7:
                candidats_indice_nom.append(colonne)

    return candidats_motif + candidats_indice_nom


def calculer_fraicheur(tableau, profil, date_reference=None):
    colonnes_date = _detecter_colonnes_date(tableau, profil)

    if not colonnes_date:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Aucune colonne temporelle détectée : la dimension fraîcheur ne s'applique pas à ce jeu de données.",
            "details": {},
        }

    colonne = colonnes_date[0]
    # Toujours convertir en texte avant le parsing : un entier brut (ex. une
    # année "2003" dans une colonne numérique) serait sinon interprété par
    # Pandas comme des nanosecondes depuis l'epoch Unix, donnant une date
    # farfelue proche de 1970.
    dates_analysees = pd.to_datetime(tableau[colonne].dropna().astype(str), errors="coerce", format="mixed")
    dates_valides = dates_analysees.dropna()

    if len(dates_valides) == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": f"Colonne temporelle '{colonne}' détectée mais aucune date n'a pu être interprétée.",
            "details": {},
        }

    reference = pd.Timestamp(date_reference) if date_reference else pd.Timestamp.now()
    plus_recente = dates_valides.max()
    age_jours = max(0, (reference - plus_recente).days)

    score = round(max(0.0, 100 - (age_jours / AGE_MAX_JOURS_POUR_SCORE_ZERO) * 100), 2)

    explication = (
        f"Colonne temporelle détectée : '{colonne}'. Enregistrement le plus récent daté du "
        f"{plus_recente.date()} ({age_jours} jours avant la date de référence)."
    )

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {
            "colonne_date": colonne,
            "date_plus_recente": str(plus_recente.date()),
            "age_jours": int(age_jours),
        },
    }
