import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --- Milestone #2 : stub du module stdlib 'resource' (Unix uniquement) ---
# insights_ia/moteur.py fait "import resource" sans garde de plateforme ; ce
# module n'existe pas sur Windows -> ModuleNotFoundError bloquant à l'import.
# Ce stub est UNIQUEMENT un contournement d'environnement de test pour rendre
# insights_ia important sur Windows : il ne corrige rien dans le code testé et
# les valeurs qu'il retourne pour la mesure mémoire ne sont PAS réelles (voir
# test du critère 12 - la partie "mesure mémoire" est marquée non fiable ici).
try:
    import resource  # noqa: F401
except ImportError:
    import types as _types

    _resource_stub = _types.ModuleType("resource")
    _resource_stub.RUSAGE_SELF = 0

    class _RUsageStub:
        ru_maxrss = 0

    _resource_stub.getrusage = lambda who: _RUsageStub()
    sys.modules["resource"] = _resource_stub

DATASET_DIR = BACKEND_DIR.parent / "dataset"

# Important : importer insights_ia.client_llm AVANT de lire GROQ_API_KEY, car c'est
# cet import qui déclenche le chargement de backend/.env via python-dotenv. Sans ce
# préchargement, os.environ.get("GROQ_API_KEY") renvoie systématiquement None ici
# (même si .env contient la clé), car conftest.py est importé avant tout appel à
# insights_ia dans les fixtures.
try:
    import insights_ia.client_llm  # noqa: F401
except Exception:  # noqa: BLE001 - si insights_ia est cassé, on le découvrira via les fixtures
    pass

GROQ_API_KEY_PRESENT = bool(os.environ.get("GROQ_API_KEY"))

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


# ============================================================
# Fixtures Milestone #2 (insights_ia)
# ============================================================


@pytest.fixture(scope="session")
def artefacts_bruts(dataset_paths):
    """artefact_analytique.construire() une seule fois par dataset pour la session."""
    import insights_ia

    resultats = {}
    for nom, chemin in dataset_paths.items():
        try:
            resultats[nom] = insights_ia.artefact_analytique.construire(str(chemin), identifiant_dataset=nom)
        except Exception as exc:  # noqa: BLE001
            resultats[nom] = exc
    return resultats


@pytest.fixture(scope="session")
def artefacts(artefacts_bruts):
    valides = {nom: a for nom, a in artefacts_bruts.items() if not isinstance(a, Exception)}
    assert valides, "Aucun artefact analytique n'a pu être construit (voir critère 1)"
    return valides


@pytest.fixture(scope="session")
def anomalies_doubles_bruts(artefacts):
    """Appelle anomalies.detecter() DEUX FOIS par artefact (nécessaire pour le
    critère 11 de reproductibilité). Le premier des deux résultats est réutilisé
    comme résultat d'anomalies pour les critères 2/4/8 afin d'éviter un 3e calcul
    (coûteux sur le dataset énergie ~2M lignes)."""
    import insights_ia

    resultats = {}
    for nom, artefact in artefacts.items():
        try:
            r1 = insights_ia.anomalies.detecter(artefact)
            r2 = insights_ia.anomalies.detecter(artefact)
            resultats[nom] = (r1, r2)
        except Exception as exc:  # noqa: BLE001
            resultats[nom] = exc
    return resultats


@pytest.fixture(scope="session")
def anomalies_doubles(anomalies_doubles_bruts):
    valides = {nom: r for nom, r in anomalies_doubles_bruts.items() if not isinstance(r, Exception)}
    assert valides, "anomalies.detecter() a échoué sur tous les datasets (voir critère 2)"
    return valides


@pytest.fixture(scope="session")
def anomalies_resultats(anomalies_doubles):
    """Un seul résultat d'anomalies par dataset (le premier des deux appels)."""
    return {nom: paire[0] for nom, paire in anomalies_doubles.items()}


@pytest.fixture(scope="session")
def visualisations_bruts(artefacts, rapports):
    import insights_ia

    resultats = {}
    for nom, artefact in artefacts.items():
        if nom not in rapports:
            continue
        try:
            resultats[nom] = insights_ia.visualisations.generer(artefact, rapports[nom]["profil"])
        except Exception as exc:  # noqa: BLE001
            resultats[nom] = exc
    return resultats


@pytest.fixture(scope="session")
def visualisations_resultats(visualisations_bruts):
    valides = {nom: r for nom, r in visualisations_bruts.items() if not isinstance(r, Exception)}
    assert valides, "visualisations.generer() a échoué sur tous les datasets (voir critère 3)"
    return valides


MODELE_LLM_DE_TEST = "openai/gpt-oss-120b"
# Le modèle par défaut codé en dur dans client_llm.py ("llama-3.3-70b-versatile")
# n'existe plus sur Groq (confirmé via /openai/v1/models : model_not_found).
# On force donc un modèle actuellement disponible via le paramètre public
# generer_rapport_intelligence(..., modele_llm=...) pour pouvoir exercer les
# critères 5/6/9 malgré ce défaut obsolète — voir le rapport de test pour le détail.


DELAI_ENTRE_APPELS_LLM_SECONDES = 65
# Le tier gratuit Groq plafonne à 8000 tokens/minute (TPM), fenêtre glissante.
# Nos prompts compressés pèsent ~4000-5500 tokens chacun : un seul appel utilise
# déjà plus de la moitié du budget, donc un délai de 18s ne suffit pas (l'appel
# précédent reste compté dans la fenêtre glissante de 60s). On attend ~65s pour
# être sûr que l'appel précédent soit totalement sorti de la fenêtre avant le
# suivant — pas un correctif du code testé, un ajustement du rythme des tests.


@pytest.fixture(scope="session")
def rapports_intelligence_bruts(dataset_paths):
    """Un seul appel à generer_rapport_intelligence() (pipeline complet) par
    dataset, réutilisé pour les critères 5, 6, 7, 8, 9 et 12."""
    import time

    import insights_ia

    resultats = {}
    noms = list(dataset_paths.items())
    for i, (nom, chemin) in enumerate(noms):
        if i > 0 and GROQ_API_KEY_PRESENT:
            time.sleep(DELAI_ENTRE_APPELS_LLM_SECONDES)
        try:
            resultats[nom] = insights_ia.generer_rapport_intelligence(
                str(chemin), modele_llm=MODELE_LLM_DE_TEST if GROQ_API_KEY_PRESENT else None
            )
        except Exception as exc:  # noqa: BLE001
            resultats[nom] = exc
    return resultats


@pytest.fixture(scope="session")
def rapports_intelligence(rapports_intelligence_bruts):
    valides = {nom: r for nom, r in rapports_intelligence_bruts.items() if not isinstance(r, Exception)}
    assert valides, "generer_rapport_intelligence() a échoué sur tous les datasets"
    return valides
