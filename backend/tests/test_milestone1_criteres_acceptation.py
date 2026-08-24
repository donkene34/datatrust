"""Tests boîte noire pour les 10 critères d'acceptation du Milestone #1
(docs/milestone_1_coeur_data_1.md). Seule la fonction publique
qualite_donnees.generer_rapport() est utilisée ; l'implémentation interne
du package n'est pas consultée.
"""

import csv
import math
from datetime import date, timedelta

import pytest

from conftest import DIMENSIONS

import qualite_donnees

TYPES_DOCUMENTES = {"int64", "float64", "str", "datetime64", "bool"}


# Critère 1 : le loader charge les 5 CSV de démo sans erreur, quel que soit le séparateur
def test_critere_01_chargement_5_datasets_sans_erreur(rapports_bruts):
    echecs = {nom: err for nom, err in rapports_bruts.items() if isinstance(err, Exception)}
    assert not echecs, f"generer_rapport() a levé une exception sur : {echecs}"

    separateurs_valides = {",", ";", "\t"}
    for nom, rapport in rapports_bruts.items():
        assert rapport.get("separateur_detecte") in separateurs_valides, (
            f"{nom}: séparateur détecté inattendu = {rapport.get('separateur_detecte')!r}"
        )


# Critère 2 : chaque dimension retourne un score entre 0 et 100 pour chacun des 5 datasets
def test_critere_02_scores_dimensions_entre_0_et_100(rapports):
    for nom, rapport in rapports.items():
        for dim in DIMENSIONS:
            score = rapport["scores_dimensions"][dim]["score"]
            assert isinstance(score, (int, float)), f"{nom}/{dim}: score non numérique ({score!r})"
            assert 0 <= score <= 100, f"{nom}/{dim}: score hors bornes = {score}"


# Critère 3 : le score global est la moyenne pondérée des 6 scores de dimension
def test_critere_03_score_global_moyenne_ponderee(rapports):
    for nom, rapport in rapports.items():
        scores = [rapport["scores_dimensions"][dim]["score"] for dim in DIMENSIONS]
        moyenne_attendue = sum(scores) / len(scores)
        assert rapport["score_global"] == pytest.approx(moyenne_attendue, abs=0.05), (
            f"{nom}: score_global={rapport['score_global']} != moyenne des dimensions ({moyenne_attendue:.2f})"
        )


# Critère 4 : sur un dataset à taux de manquants injecté connu, le score de complétude
# reflète le taux réel (tolérance ±1 point)
def test_critere_04_completude_reflete_taux_manquants_connu(tmp_path):
    chemin = tmp_path / "manquants_connus.csv"
    nb_lignes = 100
    nb_colonnes_valeur = 4  # + id
    nb_manquants_injectes = 20  # tous dans la colonne 'a'

    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "a", "b", "c", "d"])
        for i in range(nb_lignes):
            a = "" if i < nb_manquants_injectes else i
            w.writerow([i, a, i * 2, i * 3, i * 4])

    rapport = qualite_donnees.generer_rapport(str(chemin))
    completude = rapport["scores_dimensions"]["completude"]

    taux_reel = nb_manquants_injectes / (nb_lignes * nb_colonnes_valeur)
    score_attendu = 100 * (1 - taux_reel)

    assert completude["statut"] == "evalue"
    assert completude["score"] == pytest.approx(score_attendu, abs=1.0), (
        f"score complétude={completude['score']} attendu≈{score_attendu:.2f} "
        f"(taux manquants réel={taux_reel:.4f})"
    )


# Critère 5 : le rapport contient, pour chaque dimension, un champ 'score' numérique
# et un champ 'explication' texte non vide
def test_critere_05_champs_score_et_explication_presents(rapports):
    for nom, rapport in rapports.items():
        for dim in DIMENSIONS:
            bloc = rapport["scores_dimensions"][dim]
            assert "score" in bloc and isinstance(bloc["score"], (int, float)), (
                f"{nom}/{dim}: champ 'score' manquant ou non numérique"
            )
            assert "explication" in bloc and isinstance(bloc["explication"], str) and bloc["explication"].strip(), (
                f"{nom}/{dim}: champ 'explication' manquant ou vide"
            )


# Critère 6 : aucune exception non gérée, même avec colonnes 100% vides
# ou un dataset sans aucune valeur manquante (+ les 5 datasets réels, cf. critère 1)
def test_critere_06_pas_exception_cas_limites(tmp_path, rapports_bruts):
    echecs = {nom: err for nom, err in rapports_bruts.items() if isinstance(err, Exception)}
    assert not echecs, f"generer_rapport() a levé une exception sur les datasets réels : {echecs}"

    # Cas limite : une colonne 100% vide
    chemin_vide = tmp_path / "colonne_100pct_vide.csv"
    with open(chemin_vide, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "valeur", "toujours_vide"])
        for i in range(20):
            w.writerow([i, i * 2, ""])

    try:
        rapport_vide = qualite_donnees.generer_rapport(str(chemin_vide))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Exception non gérée sur colonne 100% vide : {exc!r}")
    assert "score_global" in rapport_vide

    # Cas limite : dataset sans aucune valeur manquante
    chemin_complet = tmp_path / "sans_manquants.csv"
    with open(chemin_complet, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "valeur"])
        for i in range(20):
            w.writerow([i, i * 2])

    try:
        rapport_complet = qualite_donnees.generer_rapport(str(chemin_complet))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Exception non gérée sur dataset sans valeur manquante : {exc!r}")
    assert rapport_complet["scores_dimensions"]["completude"]["score"] == pytest.approx(100.0, abs=0.01)


# Critère 7 : profileur.py retourne le contrat de données complet pour les 5 datasets
def test_critere_07_contrat_profileur_complet(rapports, dataset_paths):
    champs_colonne_attendus = {
        "nom", "type", "nb_manquants", "taux_manquants",
        "nb_valeurs_uniques", "min", "max", "moyenne", "ecart_type",
    }

    types_non_documentes_observes = set()

    for nom, rapport in rapports.items():
        profil = rapport["profil"]
        assert profil["jeu_de_donnees"] == nom
        assert "lignes" in profil["taille"] and "colonnes" in profil["taille"]
        assert profil["taille"]["lignes"] > 0
        assert profil["taille"]["colonnes"] == len(profil["colonnes"]) > 0

        for col in profil["colonnes"]:
            champs_manquants = champs_colonne_attendus - col.keys()
            assert not champs_manquants, f"{nom}/colonne {col.get('nom')}: champs manquants {champs_manquants}"

            if col["type"] not in TYPES_DOCUMENTES:
                types_non_documentes_observes.add(col["type"])

            if col["type"] in ("int64", "float64"):
                pass  # numérique : min/max peuvent être calculés (sauf colonne 100% vide, non présent ici)
            elif col["type"] not in ("int64", "float64"):
                assert col["min"] is None and col["max"] is None, (
                    f"{nom}/{col['nom']} (type={col['type']}): min/max devraient être null pour une colonne non numérique"
                )
                assert col["moyenne"] is None and col["ecart_type"] is None, (
                    f"{nom}/{col['nom']} (type={col['type']}): moyenne/ecart_type devraient être null pour une colonne non numérique"
                )

        assert "correlations" in profil and isinstance(profil["correlations"], list)
        for corr in profil["correlations"]:
            assert {"colonne_a", "colonne_b", "coefficient"} <= corr.keys()
            assert -1.0 <= corr["coefficient"] <= 1.0

    assert not types_non_documentes_observes, (
        "Le contrat documenté liste les types "
        f"{sorted(TYPES_DOCUMENTES)} pour 'colonnes[].type', mais des valeurs non documentées "
        f"ont été observées : {sorted(types_non_documentes_observes)} "
        "(pandas 'object' est utilisé à la place de 'str'/'datetime64' du contrat)"
    )


# Critère 8 : sur un dataset sans colonne date détectable, fraicheur = {score:100, statut:non_applicable}
def test_critere_08_fraicheur_non_applicable_sans_colonne_date(rapports):
    nom = "WA_Fn-UseC_-HR-Employee-Attrition.csv"
    assert nom in rapports, f"dataset {nom} indisponible (voir critère 1)"
    fraicheur = rapports[nom]["scores_dimensions"]["fraicheur"]

    assert "statut" in fraicheur
    assert fraicheur["statut"] == "non_applicable"
    assert fraicheur["statut"] != "evalue"
    assert fraicheur["score"] == pytest.approx(100.0, abs=0.01)


# Critère 9 : sur un dataset avec colonne date valide, fraicheur = statut 'evalue'
# avec un score qui reflète réellement la pertinence temporelle (pas une valeur figée)
def test_critere_09_fraicheur_evalue_reflete_pertinence_temporelle(tmp_path):
    def construire_csv(chemin, dates):
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "date_evenement", "valeur"])
            for i, d in enumerate(dates):
                w.writerow([i, d.isoformat(), i])

    aujourd_hui = date.today()
    chemin_frais = tmp_path / "dates_fraiches.csv"
    chemin_vieux = tmp_path / "dates_vieilles.csv"
    construire_csv(chemin_frais, [aujourd_hui - timedelta(days=i) for i in range(30)])
    construire_csv(chemin_vieux, [aujourd_hui - timedelta(days=3650 + i) for i in range(30)])

    rapport_frais = qualite_donnees.generer_rapport(str(chemin_frais))
    rapport_vieux = qualite_donnees.generer_rapport(str(chemin_vieux))

    fraicheur_frais = rapport_frais["scores_dimensions"]["fraicheur"]
    fraicheur_vieux = rapport_vieux["scores_dimensions"]["fraicheur"]

    assert fraicheur_frais["statut"] == "evalue"
    assert fraicheur_vieux["statut"] == "evalue"

    assert fraicheur_frais["score"] == pytest.approx(100.0, abs=1.0), (
        "un dataset avec des dates très récentes devrait avoir un score de fraîcheur proche de 100"
    )
    assert fraicheur_vieux["score"] < fraicheur_frais["score"] - 50, (
        f"le score de fraîcheur ne semble pas refléter la pertinence temporelle réelle : "
        f"frais={fraicheur_frais['score']} vieux={fraicheur_vieux['score']}"
    )


# Critère 10 : validite.py ne signale aucune erreur sur des valeurs métier légitimes
# mais statistiquement inhabituelles (ex. âge=95)
def test_critere_10_validite_pas_de_faux_positifs_sur_valeurs_legitimes(tmp_path):
    chemin = tmp_path / "valeurs_legitimes_inhabituelles.csv"
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "age", "revenu_annuel"])
        for i in range(20):
            w.writerow([i, 30, 40000])
        # valeurs métier légitimes mais statistiquement atypiques (pas des erreurs de saisie)
        w.writerow([20, 95, 40000])
        w.writerow([21, 18, 1000000])

    rapport = qualite_donnees.generer_rapport(str(chemin))
    validite = rapport["scores_dimensions"]["validite"]

    assert validite["score"] == pytest.approx(100.0, abs=0.01), (
        f"validite a pénalisé des valeurs métier légitimes (âge=95, revenu=1M) : {validite}"
    )
    assert validite["details"]["nb_invalides"] == 0
