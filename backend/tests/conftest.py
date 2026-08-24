import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DATASET_DIR = BACKEND_DIR.parent / "dataset"

DIMENSIONS = ["completude", "coherence", "unicite", "validite", "aberrations", "fraicheur"]

DATASETS_DEMO = [
    "WA_Fn-UseC_-HR-Employee-Attrition.csv",
    "bank_transactions_data_2.csv",
    "household_power_consumption.txt",
    "realworld_medical_dirty.csv",
    "train.csv",
]


@pytest.fixture(scope="session")
def dataset_paths():
    chemins = {nom: DATASET_DIR / nom for nom in DATASETS_DEMO}
    manquants = [nom for nom, chemin in chemins.items() if not chemin.exists()]
    assert not manquants, f"Datasets de démonstration introuvables dans {DATASET_DIR}: {manquants}"
    return chemins


@pytest.fixture(scope="session")
def rapports_bruts(dataset_paths):
    """Calcule generer_rapport() une seule fois par dataset pour toute la session
    (le dataset énergie fait 2M lignes, coûteux à recalculer par test)."""
    import qualite_donnees

    resultats = {}
    for nom, chemin in dataset_paths.items():
        try:
            resultats[nom] = qualite_donnees.generer_rapport(str(chemin))
        except Exception as exc:  # noqa: BLE001 - on capture pour le rapport de test
            resultats[nom] = exc
    return resultats


@pytest.fixture(scope="session")
def rapports(rapports_bruts):
    """Sous-ensemble des rapports ayant réussi (voir test du critère 1/6 pour les échecs)."""
    valides = {nom: r for nom, r in rapports_bruts.items() if not isinstance(r, Exception)}
    assert valides, "Aucun dataset n'a pu être traité par generer_rapport() (voir critère 1)"
    return valides
