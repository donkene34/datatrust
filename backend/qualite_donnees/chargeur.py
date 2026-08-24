"""
chargeur.py — Chargement d'un fichier CSV en tableau Pandas.

Détecte automatiquement le séparateur (`,` `;` `\\t` `|`) car les datasets de
démonstration du projet n'utilisent pas tous le même (ex. `;` pour un export
type UCI). Reconnaît également plusieurs représentations textuelles de valeur
manquante ("N/A", "null", "?", etc.) en plus de la détection Pandas standard.
"""

import csv
import pandas as pd

SEPARATEURS_CANDIDATS = [",", ";", "\t", "|"]

VALEURS_NA_SUPPLEMENTAIRES = [
    "", "NA", "N/A", "n/a", "null", "NULL", "Null",
    "None", "none", "?", "-", "--", "unknown", "Unknown", "missing", "MISSING",
]


def detecter_separateur(chemin_fichier, taille_echantillon=8192):
    """Devine le séparateur du fichier CSV à partir d'un échantillon."""
    with open(chemin_fichier, "r", encoding="utf-8", errors="ignore") as f:
        echantillon = f.read(taille_echantillon)

    try:
        dialecte = csv.Sniffer().sniff(echantillon, delimiters="".join(SEPARATEURS_CANDIDATS))
        if dialecte.delimiter in SEPARATEURS_CANDIDATS:
            return dialecte.delimiter
    except csv.Error:
        pass

    # Repli : le séparateur le plus fréquent dans l'échantillon
    comptes = {sep: echantillon.count(sep) for sep in SEPARATEURS_CANDIDATS}
    meilleur = max(comptes, key=comptes.get)
    return meilleur if comptes[meilleur] > 0 else ","


def charger_csv(chemin_fichier):
    """
    Charge un fichier CSV en tableau Pandas.

    Retourne (tableau, separateur_detecte).
    Lève ValueError si le fichier ne peut pas être interprété comme un tableau
    (ex. fichier vide ou binaire) plutôt que de laisser Pandas planter avec
    une exception peu lisible.
    """
    separateur = detecter_separateur(chemin_fichier)

    try:
        tableau = pd.read_csv(
            chemin_fichier,
            sep=separateur,
            engine="python",
            na_values=VALEURS_NA_SUPPLEMENTAIRES,
            keep_default_na=True,
            on_bad_lines="skip",
        )
    except Exception as exc:  # pragma: no cover - filet de sécurité générique
        raise ValueError(f"Impossible de charger '{chemin_fichier}' comme CSV : {exc}") from exc

    if tableau.shape[1] == 0:
        raise ValueError(f"Aucune colonne détectée dans '{chemin_fichier}' — vérifier le format du fichier.")

    return tableau, separateur
