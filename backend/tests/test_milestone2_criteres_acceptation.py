"""Tests boîte noire pour les 12 critères d'acceptation du Milestone #2
(docs/milestone_2_intelligence.md). Seule l'API publique de insights_ia est
utilisée (introspectée via inspect.signature) ; l'implémentation interne du
package n'est pas consultée.

Note d'environnement (historique) : une première version de insights_ia/moteur.py
importait le module stdlib 'resource' (Unix uniquement), cassant l'import sur
Windows ; un stub de secours reste posé dans conftest.py par précaution. Ce point
est corrigé depuis (moteur.py utilise psutil, cross-platform) : confirmé en
important insights_ia sans ce stub, et la mesure mémoire du critère 12 est donc
une vraie mesure système, pleinement validée ci-dessous.
"""

import base64
import json
import os
import subprocess

import pytest

from conftest import BACKEND_DIR, GROQ_API_KEY_PRESENT

import insights_ia
import qualite_donnees

NOMBRE_ANOMALIES_EXTREMES_ATTENDU = 10


# Critère 1 : artefact_analytique.construire() s'exécute sans erreur sur les 5 datasets ;
# matrice_features ne contient aucun NaN ; les colonnes >50% manquantes sont dans colonnes_exclues
def test_critere_01_artefact_analytique_contrat(artefacts_bruts, tmp_path):
    import numpy as np

    echecs = {nom: err for nom, err in artefacts_bruts.items() if isinstance(err, Exception)}
    assert not echecs, f"artefact_analytique.construire() a levé une exception sur : {echecs}"

    for nom, artefact in artefacts_bruts.items():
        for champ in (
            "identifiant_dataset", "nombre_observations", "colonnes_numeriques",
            "colonnes_exclues", "matrice_features", "metadonnees_transformation",
        ):
            assert champ in artefact, f"{nom}: champ '{champ}' manquant dans l'artefact"

        matrice = artefact["matrice_features"]
        assert not np.isnan(matrice).any(), f"{nom}: la matrice_features contient des NaN"
        assert matrice.shape[0] == artefact["nombre_observations"]
        assert matrice.shape[1] == len(artefact["colonnes_numeriques"])

    # Cas synthétique : une colonne numérique à >50% de valeurs manquantes doit être exclue
    chemin = tmp_path / "colonne_tres_manquante.csv"
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["id", "bonne_colonne", "colonne_tres_manquante"])
        for i in range(100):
            val = "" if i < 60 else i  # 60% manquant > seuil 50%
            w.writerow([i, i * 2, val])

    artefact_synth = insights_ia.artefact_analytique.construire(str(chemin))
    noms_exclus = [c["nom"] for c in artefact_synth["colonnes_exclues"]]
    assert "colonne_tres_manquante" in noms_exclus, (
        f"une colonne à 60% de manquants devrait être exclue, colonnes_exclues={artefact_synth['colonnes_exclues']}"
    )
    assert "colonne_tres_manquante" not in artefact_synth["colonnes_numeriques"]
    assert not np.isnan(artefact_synth["matrice_features"]).any()


# Critère 2 : anomalies.py s'exécute sans erreur sur les 5 datasets et retourne une liste
# d'anomalies multivariées (potentiellement vide), chaque anomalie référençant un score
# et les colonnes numériques utilisées
def test_critere_02_anomalies_detection_multivariee(anomalies_doubles_bruts, artefacts):
    echecs = {nom: err for nom, err in anomalies_doubles_bruts.items() if isinstance(err, Exception)}
    assert not echecs, f"anomalies.detecter() a levé une exception sur : {echecs}"

    for nom, (resultat, _r2) in anomalies_doubles_bruts.items():
        assert "anomalies" in resultat
        anomalies_liste = resultat["anomalies"]
        assert isinstance(anomalies_liste, list)

        colonnes_attendues = set(artefacts[nom]["colonnes_numeriques"])
        for anomalie in anomalies_liste:
            assert "score" in anomalie and isinstance(anomalie["score"], (int, float)), (
                f"{nom}: une anomalie sans champ 'score' numérique : {anomalie}"
            )
            assert "colonnes" in anomalie and anomalie["colonnes"], (
                f"{nom}: une anomalie sans colonnes numériques référencées : {anomalie}"
            )
            assert set(anomalie["colonnes"]) <= colonnes_attendues


# Critère 3 : visualisations.py génère au moins 2 graphiques par dataset (histogramme,
# heatmap de corrélations), encodés en base64 valides (décodables en image)
def test_critere_03_visualisations_generees(visualisations_bruts):
    echecs = {nom: err for nom, err in visualisations_bruts.items() if isinstance(err, Exception)}
    assert not echecs, f"visualisations.generer() a levé une exception sur : {echecs}"

    for nom, resultat in visualisations_bruts.items():
        images = resultat["images"]
        assert len(images) >= 2, f"{nom}: moins de 2 graphiques générés ({list(images.keys())})"
        assert "histogramme" in images
        assert "heatmap_correlations" in images or "heatmap" in images

        for cle, b64 in images.items():
            try:
                brut = base64.b64decode(b64, validate=True)
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"{nom}/{cle}: base64 invalide ({exc})")
            assert brut[:8] == b"\x89PNG\r\n\x1a\n", f"{nom}/{cle}: contenu décodé non reconnu comme PNG"


# Critère 4 : le prompt construit par invite.py ne contient ni valeur de cellule
# individuelle, ni la matrice_features, ni de base64 d'image, ni la liste complète des
# anomalies — uniquement des agrégats + les 10 anomalies aux scores les plus extrêmes.
# Le prompt système distingue anomalie statistique et anomalie métier.
def test_critere_04_prompt_ne_contient_que_des_agregats(rapports, anomalies_resultats, visualisations_resultats):
    noms_communs = set(rapports) & set(anomalies_resultats) & set(visualisations_resultats)
    assert noms_communs, "aucun dataset disponible pour construire un prompt"

    for nom in noms_communs:
        prompt_systeme, prompt_utilisateur = insights_ia.invite.construire_prompt(
            rapports[nom], anomalies_resultats[nom], visualisations_resultats[nom]["resume_pour_prompt"]
        )
        assert isinstance(prompt_systeme, str) and prompt_systeme.strip()
        assert isinstance(prompt_utilisateur, str) and prompt_utilisateur.strip()

        # Pas de base64 d'image dans le prompt (les images PNG produites commencent par ce motif base64)
        assert "iVBORw0KGgo" not in prompt_utilisateur, f"{nom}: une image base64 fuite dans le prompt"
        # Pas la matrice_features brute
        assert "matrice_features" not in prompt_utilisateur, f"{nom}: 'matrice_features' référencée dans le prompt"
        # Pas la liste complète des anomalies (champ 'indice_observation' = clé de la liste complète
        # retournée par anomalies.detecter(), distincte de 'indice' utilisé pour les 10 extrêmes)
        assert "indice_observation" not in prompt_utilisateur, (
            f"{nom}: la liste complète des anomalies (champ 'indice_observation') semble présente dans le prompt"
        )

        # Extraction structurée du bloc de données JSON du prompt utilisateur pour vérifier
        # la limite des 10 anomalies les plus extrêmes
        marqueur = "Données fournies :"
        assert marqueur in prompt_utilisateur, f"{nom}: bloc de données introuvable dans le prompt utilisateur"
        bloc_json = prompt_utilisateur[prompt_utilisateur.find(marqueur) + len(marqueur):].strip()
        donnees = json.loads(bloc_json)

        resume_anomalies = donnees.get("resume_anomalies", {})
        extremes = resume_anomalies.get("anomalies_les_plus_extremes")
        assert extremes is not None, f"{nom}: 'anomalies_les_plus_extremes' absent du prompt"
        nb_anomalies_reelles = len(anomalies_resultats[nom]["anomalies"])
        assert len(extremes) == min(NOMBRE_ANOMALIES_EXTREMES_ATTENDU, nb_anomalies_reelles), (
            f"{nom}: {len(extremes)} anomalies extrêmes transmises, attendu "
            f"min({NOMBRE_ANOMALIES_EXTREMES_ATTENDU}, {nb_anomalies_reelles})"
        )
        # Le résumé ne doit pas contenir la liste complète (uniquement le sous-ensemble extrême)
        assert len(extremes) <= NOMBRE_ANOMALIES_EXTREMES_ATTENDU

        # Le prompt système doit imposer la distinction anomalie statistique / anomalie métier
        systeme_minuscule = prompt_systeme.lower()
        assert "statistique" in systeme_minuscule
        assert any(mot in systeme_minuscule for mot in ("erreur", "fraude", "pathologique")), (
            f"{nom}: le prompt système ne semble pas rappeler la distinction anomalie statistique/métier"
        )


# Critères 5 et 6 : contrat de sortie du LLM (nécessitent GROQ_API_KEY) — skip si absente
# Les deux tests ne s'arrêtent PAS au premier dataset en échec : chaque dataset est
# évalué indépendamment et le détail PASS/FAIL de chacun est rapporté à la fin.
@pytest.mark.skipif(not GROQ_API_KEY_PRESENT, reason="GROQ_API_KEY absente : contrat LLM non testable (voir critère 7)")
def test_critere_05_contrat_sortie_llm_reussi(rapports_intelligence):
    resultats = {}
    for nom, rapport in rapports_intelligence.items():
        insights = rapport["insights_ia"]
        problemes = []
        if "erreur" in insights:
            problemes.append(f"appel LLM en échec : {insights['erreur']}")
        else:
            if not (isinstance(insights.get("resume"), str) and insights["resume"].strip()):
                problemes.append("'resume' manquant ou vide")
            if not (isinstance(insights.get("recommandations"), list) and len(insights["recommandations"]) >= 1):
                problemes.append(f"'recommandations' invalide : {insights.get('recommandations')!r}")
            for insight in insights.get("insights", []):
                for champ in ("titre", "description", "importance", "source"):
                    if not insight.get(champ):
                        problemes.append(f"insight incomplet, champ '{champ}' vide : {insight}")
        resultats[nom] = problemes

    rapport_final = "\n".join(
        f"  [{'FAIL' if problemes else 'PASS'}] {nom}" + (f" -> {'; '.join(problemes)}" if problemes else "")
        for nom, problemes in resultats.items()
    )
    print("\n--- Détail critère 5 par dataset ---\n" + rapport_final)
    assert not any(resultats.values()), "Critère 5 en échec sur au moins un dataset :\n" + rapport_final


@pytest.mark.skipif(not GROQ_API_KEY_PRESENT, reason="GROQ_API_KEY absente : contrat 'source' non testable (voir critère 7)")
def test_critere_06_source_structuree_et_verifiable(rapports_intelligence):
    types_valides = {"statistique", "anomalie", "correlation"}
    resultats = {}
    for nom, rapport in rapports_intelligence.items():
        insights = rapport["insights_ia"]
        problemes = []
        if "erreur" in insights:
            problemes.append(f"appel LLM en échec : {insights['erreur']}")
        elif not insights.get("insights"):
            problemes.append("aucun insight retourné, rien à vérifier pour le critère 6")
        else:
            for insight in insights.get("insights", []):
                source = insight.get("source")
                if not isinstance(source, dict):
                    problemes.append(f"source non structurée : {source!r}")
                    continue
                for champ in ("type", "element", "metrique", "valeur"):
                    if champ not in source:
                        problemes.append(f"champ '{champ}' manquant dans source={source}")
                if source.get("type") not in types_valides:
                    problemes.append(f"type de source invalide : {source.get('type')!r}")
        resultats[nom] = problemes

    rapport_final = "\n".join(
        f"  [{'FAIL' if problemes else 'PASS'}] {nom}" + (f" -> {'; '.join(problemes)}" if problemes else "")
        for nom, problemes in resultats.items()
    )
    print("\n--- Détail critère 6 par dataset ---\n" + rapport_final)
    assert not any(resultats.values()), "Critère 6 en échec sur au moins un dataset :\n" + rapport_final


# Critère 7 : si la clé API est absente ou invalide, le moteur retourne {"erreur": "..."}
# sans exception ; les sections qualité/profil/anomalies/visualisations restent présentes
def test_critere_07_degradation_gracieuse_cle_absente(rapports_intelligence):
    if GROQ_API_KEY_PRESENT:
        pytest.skip("GROQ_API_KEY présente dans cet environnement : le cas 'clé absente' n'est pas exercé ici")

    for nom, rapport in rapports_intelligence.items():
        assert "erreur" in rapport["insights_ia"], f"{nom}: pas de champ 'erreur' alors que GROQ_API_KEY est absente"
        assert isinstance(rapport["insights_ia"]["erreur"], str) and rapport["insights_ia"]["erreur"].strip()

        assert rapport["qualite"]["score_global"] is not None
        assert "profil" in rapport["qualite"]
        assert isinstance(rapport["anomalies"]["anomalies"], list)
        assert "images" in rapport["visualisations"]


def test_critere_07_degradation_gracieuse_cle_invalide(dataset_paths, monkeypatch):
    """Complément : simule une clé invalide (plutôt qu'absente) avec une fausse valeur,
    pour vérifier l'autre branche de l'ADR-5 sans exposer de vraie clé."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_fake_secret_pour_verification_9f3e7a")
    chemin = dataset_paths["WA_Fn-UseC_-HR-Employee-Attrition.csv"]

    try:
        rapport = insights_ia.generer_rapport_intelligence(str(chemin))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Exception non gérée avec une clé API invalide : {exc!r}")

    assert "erreur" in rapport["insights_ia"], f"pas de dégradation gracieuse avec une clé invalide : {rapport['insights_ia']}"
    assert isinstance(rapport["anomalies"]["anomalies"], list)
    assert "images" in rapport["visualisations"]


# Critère 8 : le JSON final combine bien les 4 blocs : qualité, anomalies, visualisations, insights IA
def test_critere_08_json_final_combine_4_blocs(rapports_intelligence):
    for nom, rapport in rapports_intelligence.items():
        for bloc in ("qualite", "anomalies", "visualisations", "insights_ia"):
            assert bloc in rapport, f"{nom}: bloc '{bloc}' absent du JSON final"
        assert rapport["qualite"]["jeu_de_donnees"] == nom
        assert "anomalies" in rapport["anomalies"]
        assert "images" in rapport["visualisations"]


# Critère 9 : aucune clé API n'apparaît dans le JSON de sortie ni dans les logs
def test_critere_09_pas_de_cle_api_dans_la_sortie(dataset_paths, monkeypatch, capsys):
    fausse_cle = "gsk_test_fake_secret_pour_verification_9f3e7a"
    monkeypatch.setenv("GROQ_API_KEY", fausse_cle)
    chemin = dataset_paths["WA_Fn-UseC_-HR-Employee-Attrition.csv"]

    rapport = insights_ia.generer_rapport_intelligence(str(chemin))

    serialise = json.dumps(rapport, ensure_ascii=False)
    assert fausse_cle not in serialise, "la clé API (fausse, pour test) apparaît dans le JSON de sortie"

    sortie_capturee = capsys.readouterr()
    assert fausse_cle not in sortie_capturee.out, "la clé API (fausse, pour test) apparaît dans stdout"
    assert fausse_cle not in sortie_capturee.err, "la clé API (fausse, pour test) apparaît dans stderr"


# Critère 10 : aucune modification détectée dans backend/qualite_donnees/ depuis la validation du Milestone 1
def test_critere_10_qualite_donnees_inchange():
    log = subprocess.run(
        ["git", "log", "--oneline", "--grep=Milestone 1"],
        cwd=str(BACKEND_DIR.parent), capture_output=True, text=True, check=True,
    )
    lignes = [l for l in log.stdout.strip().splitlines() if l.strip()]
    assert lignes, "commit de validation du Milestone 1 introuvable dans l'historique git"
    commit_validation = lignes[-1].split()[0]  # le plus ancien match = validation initiale

    diff = subprocess.run(
        ["git", "diff", "--name-only", commit_validation, "--", "backend/qualite_donnees/"],
        cwd=str(BACKEND_DIR.parent), capture_output=True, text=True, check=True,
    )
    fichiers_modifies = [l for l in diff.stdout.strip().splitlines() if l.strip()]
    assert not fichiers_modifies, (
        f"backend/qualite_donnees/ a été modifié depuis {commit_validation} : {fichiers_modifies}"
    )

    statut = subprocess.run(
        ["git", "status", "--porcelain", "--", "backend/qualite_donnees/"],
        cwd=str(BACKEND_DIR.parent), capture_output=True, text=True, check=True,
    )
    assert not statut.stdout.strip(), f"modifications non commitées détectées : {statut.stdout}"


# Critère 11 : deux exécutions successives d'anomalies.py sur le même dataset produisent
# exactement les mêmes scores d'anomalie pour chaque observation (random_state fixe)
def test_critere_11_reproductibilite_isolation_forest(anomalies_doubles):
    for nom, (r1, r2) in anomalies_doubles.items():
        assert r1["parametres"] == r2["parametres"], f"{nom}: paramètres différents entre les 2 exécutions"
        assert r1["nombre_anomalies_detectees"] == r2["nombre_anomalies_detectees"], (
            f"{nom}: nombre d'anomalies différent entre les 2 exécutions"
        )
        assert r1["taux_anomalies"] == r2["taux_anomalies"]

        scores_1 = {a["indice_observation"]: a["score"] for a in r1["anomalies"]}
        scores_2 = {a["indice_observation"]: a["score"] for a in r2["anomalies"]}
        assert scores_1 == scores_2, (
            f"{nom}: les scores d'anomalie par observation diffèrent entre les 2 exécutions "
            f"malgré le random_state fixe (ADR-1)"
        )


# Critère 12 : sur le dataset énergie, le pipeline mesure et journalise le temps de
# chargement, de construction de l'artefact, d'Isolation Forest, de visualisations, et
# la mémoire — valeurs présentes, non nulles, non anormalement élevées
def test_critere_12_mesures_de_performance_temps(rapports_intelligence):
    nom_energie = "household_power_consumption.txt"
    assert nom_energie in rapports_intelligence, f"{nom_energie} indisponible (voir critère 1/8)"
    perf = rapports_intelligence[nom_energie]["performance"]

    champs_temps = [
        "temps_chargement_secondes",
        "temps_construction_artefact_secondes",
        "temps_anomalies_secondes",
        "temps_visualisations_secondes",
    ]
    for champ in champs_temps:
        assert champ in perf, f"champ de performance manquant : {champ}"
        valeur = perf[champ]
        assert isinstance(valeur, (int, float)), f"{champ} n'est pas numérique : {valeur!r}"
        assert valeur > 0, f"{champ} devrait être > 0 sur ~2M lignes, obtenu {valeur}"
        assert valeur < 300, f"{champ}={valeur}s semble anormalement élevé (pipeline peu utilisable en pratique)"


def test_critere_12_mesure_memoire_champ_present(rapports_intelligence):
    """insights_ia est désormais importable nativement sur Windows sans le stub
    'resource' de conftest.py (confirmé : moteur.py utilise maintenant psutil,
    cross-platform). La mesure mémoire est donc une vraie mesure système ici, pas
    une valeur stubbée — on la valide pleinement (présence, type, non-nullité,
    plage plausible pour ~2M lignes)."""
    nom_energie = "household_power_consumption.txt"
    perf = rapports_intelligence[nom_energie]["performance"]

    assert "memoire_maximale_mo" in perf
    valeur = perf["memoire_maximale_mo"]
    assert isinstance(valeur, (int, float)), f"memoire_maximale_mo n'est pas numérique : {valeur!r}"
    assert valeur > 0, f"memoire_maximale_mo devrait être > 0 sur ~2M lignes, obtenu {valeur}"
    assert valeur < 8192, f"memoire_maximale_mo={valeur} Mo semble anormalement élevé (pipeline peu utilisable en pratique)"
