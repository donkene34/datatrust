"""
Dimension : validité — voir Milestone #1 V2, ADR-6.

Périmètre strictement limité aux règles automatiquement inférables, SANS
connaissance métier :
  - valeurs infinies (inf / -inf) dans les colonnes numériques
  - valeurs manquantes déguisées en texte ("null", "n/a", "?", ...) non
    déjà reconnues par le loader
  - colonnes ressemblant à des dates : dates invalides (non interprétables)
    et mélange de formats de date au sein de la même colonne

Explicitement HORS PÉRIMÈTRE : toute règle nécessitant une connaissance du
domaine (ex. "un âge ne peut pas être négatif"). Ces règles métier ne sont
pas évaluées ici pour éviter de signaler à tort des valeurs légitimes mais
statistiquement inhabituelles.
"""

import re

import numpy as np
import pandas as pd

from ..utilitaires_type import est_type_textuel

MOTIFS_DATE = [
    r"^\d{4}-\d{2}-\d{2}",     # AAAA-MM-JJ
    r"^\d{2}/\d{2}/\d{4}",     # JJ/MM/AAAA ou MM/JJ/AAAA
    r"^\d{2}-\d{2}-\d{4}",     # JJ-MM-AAAA
]

VALEURS_NA_DEGUISEES = {"nan", "null", "n/a", "na", "none", "?", "-", "--", "unknown", "missing"}


def _ressemble_a_colonne_date(echantillon_serie):
    if len(echantillon_serie) == 0:
        return False
    correspondances = sum(any(re.match(p, v.strip()) for p in MOTIFS_DATE) for v in echantillon_serie)
    return correspondances / len(echantillon_serie) > 0.5


def calculer_validite(tableau, profil):
    total_verifie = 0
    nb_invalides = 0
    problemes = []

    for infos_colonne in profil["colonnes"]:
        colonne = infos_colonne["nom"]
        serie = tableau[colonne]
        non_nuls = serie.dropna()
        if len(non_nuls) == 0:
            continue

        invalides_colonne = 0

        if pd.api.types.is_numeric_dtype(serie):
            total_verifie += len(non_nuls)
            nb_infinis = int(np.isinf(non_nuls.astype(float)).sum())
            invalides_colonne += nb_infinis

        elif est_type_textuel(serie):
            valeurs_str = non_nuls.astype(str).str.strip().str.lower()
            total_verifie += len(non_nuls)

            deguisees = int(valeurs_str.isin(VALEURS_NA_DEGUISEES).sum())
            invalides_colonne += deguisees

            echantillon = non_nuls.astype(str).head(50).tolist()
            if _ressemble_a_colonne_date(echantillon):
                dates_analysees = pd.to_datetime(non_nuls.astype(str), errors="coerce", format="mixed")
                dates_invalides = int(dates_analysees.isna().sum())
                invalides_colonne += dates_invalides

                motifs_utilises = set()
                for v in non_nuls.astype(str).head(200):
                    for i, p in enumerate(MOTIFS_DATE):
                        if re.match(p, v.strip()):
                            motifs_utilises.add(i)
                            break
                if len(motifs_utilises) > 1:
                    problemes.append(f"{colonne}: formats de date mélangés au sein de la même colonne")

        if invalides_colonne > 0:
            taux = invalides_colonne / len(non_nuls)
            problemes.append(f"{colonne}: {invalides_colonne} valeur(s) invalide(s) détectée(s) ({taux * 100:.1f}%)")

        nb_invalides += invalides_colonne

    if total_verifie == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Aucune colonne éligible aux contrôles de validité automatiques.",
            "details": {},
        }

    taux = nb_invalides / total_verifie
    score = round(max(0.0, 100 - taux * 100), 2)
    explication = (
        "; ".join(problemes[:3])
        if problemes
        else "Aucune valeur invalide détectée selon les règles automatiques (type, dates, valeurs infinies, NA déguisées)."
    )

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {"nb_invalides": nb_invalides, "problemes": problemes},
    }
