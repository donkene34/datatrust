"""
Script de démonstration du Moteur de Qualité des Données (Milestone #1).

Usage :
    python lancer_rapports.py

Parcourt tous les CSV du dossier dataset/ (à la racine du dépôt), génère un
rapport de qualité pour chacun, l'affiche en résumé et l'enregistre en JSON
dans backend/rapports/.
"""

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")  # avertissements de parsing de dates non bloquants

sys.path.insert(0, os.path.dirname(__file__))

from qualite_donnees import generer_rapport  # noqa: E402

DOSSIER_DATASETS = os.path.join(os.path.dirname(__file__), "..", "dataset")
DOSSIER_SORTIE = os.path.join(os.path.dirname(__file__), "rapports")


def main():
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    if not os.path.isdir(DOSSIER_DATASETS):
        print(f"Dossier introuvable : {DOSSIER_DATASETS}")
        return

    fichiers_csv = [f for f in os.listdir(DOSSIER_DATASETS) if f.lower().endswith(".csv")]
    if not fichiers_csv:
        print(f"Aucun fichier CSV trouvé dans {DOSSIER_DATASETS}")
        return

    for nom_fichier in sorted(fichiers_csv):
        chemin_fichier = os.path.join(DOSSIER_DATASETS, nom_fichier)
        print("=" * 70)
        print(nom_fichier)
        try:
            rapport = generer_rapport(chemin_fichier)
        except ValueError as exc:
            print(f"  Échec du chargement : {exc}")
            continue

        print(f"  Score global : {rapport['score_global']}/100")
        for dim, resultat in rapport["scores_dimensions"].items():
            print(f"    - {dim:<13} {resultat['score']:>6}/100  [{resultat['statut']}]  {resultat['explication']}")

        chemin_sortie = os.path.join(DOSSIER_SORTIE, nom_fichier.replace(".csv", ".json"))
        with open(chemin_sortie, "w", encoding="utf-8") as f:
            json.dump(rapport, f, ensure_ascii=False, indent=2)
        print(f"  Rapport enregistré : {chemin_sortie}")


if __name__ == "__main__":
    main()
