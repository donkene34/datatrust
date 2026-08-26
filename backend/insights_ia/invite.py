"""
invite.py — Construit le prompt structuré envoyé au LLM (client_llm.py).

Le prompt ne contient JAMAIS : le CSV brut, la matrice_features de
l'artefact analytique, une observation individuelle du dataset, la liste
complète des anomalies détectées, ou une image encodée en base64
(ADR-3, ADR-10). Il ne contient QUE des agrégats déjà calculés par les
étapes précédentes du pipeline : le rapport qualité (Milestone #1), un
résumé compressé des anomalies (Milestone #2, ADR-10), et des statistiques
descriptives des visualisations (jamais les images elles-mêmes).
"""

import json

NOMBRE_ANOMALIES_EXTREMES = 10
NOMBRE_CORRELATIONS_FORTES = 10
NOMBRE_COLONNES_DETAILLEES = 25

PROMPT_SYSTEME = """Tu es un assistant d'analyse de données pour une plateforme de certification de datasets ("Data Trust & Insights").
Tu reçois des résultats DÉJÀ CALCULÉS (rapport qualité, résumé d'anomalies, statistiques de visualisations) — jamais les données brutes du dataset.

Règles strictes :
1. Réponds UNIQUEMENT en JSON valide, respectant exactement le contrat de sortie fourni. Aucun texte hors du JSON.
2. Chaque insight doit inclure un champ "source" structuré ({"type", "element", "metrique", "valeur"}) qui référence une valeur RÉELLEMENT présente dans les données fournies ci-dessous. N'invente jamais une source.
3. Ne vise PAS un nombre fixe d'insights : propose autant d'insights que les données le justifient réellement (cible de 3 minimum si les données le permettent), jamais un insight inventé pour atteindre un quota. En revanche, le champ "recommandations" est OBLIGATOIRE et doit toujours contenir au moins 1 élément, même si peu d'insights sont proposés — une recommandation peut porter sur la qualité des données elles-mêmes (ex. "vérifier telle colonne") si aucune autre ne se justifie.
4. Une anomalie détectée par Isolation Forest est une anomalie STATISTIQUE (une observation isolable selon le modèle et ses paramètres) — ce n'est PAS automatiquement une erreur, une fraude ou une donnée pathologique. N'affirme jamais catégoriquement qu'un pourcentage de données est "incorrect" ou "invalide" à partir de ce seul résultat ; utilise des formulations prudentes du type "mérite une investigation complémentaire".
5. Si le taux d'anomalies est élevé, ne le présente pas comme suspect en soi : rappelle la méthode et les paramètres utilisés (contamination, random_state) avant toute interprétation.
"""

CONTRAT_SORTIE = {
    "resume": "...",
    "insights": [
        {
            "titre": "...",
            "description": "...",
            "importance": "elevee | moyenne | faible",
            "source": {
                "type": "statistique | anomalie | correlation",
                "element": "...",
                "metrique": "...",
                "valeur": 0,
            },
        }
    ],
    "recommandations": [{"titre": "...", "description": "..."}],
}


def _resumer_anomalies(resultat_anomalies):
    """
    Compresse la sortie complète de anomalies.detecter() (ADR-9) en un
    résumé exploitable par le LLM (ADR-10) : jamais la liste complète des
    anomalies, uniquement des statistiques + les N anomalies aux scores les
    plus extrêmes (les plus négatifs = les plus atypiques).
    """
    anomalies = resultat_anomalies.get("anomalies", [])
    anomalies_triees = sorted(anomalies, key=lambda a: a["score"])
    extremes = anomalies_triees[:NOMBRE_ANOMALIES_EXTREMES]

    scores = [a["score"] for a in anomalies]

    return {
        "methode": resultat_anomalies.get("methode"),
        "parametres": resultat_anomalies.get("parametres"),
        "nombre_observations": resultat_anomalies.get("nombre_observations_analysees"),
        "nombre_anomalies": resultat_anomalies.get("nombre_anomalies_detectees"),
        "taux_anomalies": resultat_anomalies.get("taux_anomalies"),
        "score_min": round(min(scores), 4) if scores else None,
        "score_max": round(max(scores), 4) if scores else None,
        "colonnes_utilisees": resultat_anomalies.get("colonnes_utilisees"),
        "anomalies_les_plus_extremes": [
            {"indice": a["indice_observation"], "score": a["score"]} for a in extremes
        ],
    }


def _comprimer_correlations(correlations):
    """
    Compresse la liste des corrélations du profil Milestone #1 (ADR-10,
    étendu ici au-delà des seules anomalies — trouvé en test réel : sur un
    dataset à 24 colonnes numériques, les 276 paires possibles pesaient à
    elles seules près de la moitié du prompt, l'immense majorité étant des
    corrélations faibles et sans intérêt pour le LLM). Ne garde que les N
    corrélations les plus fortes en valeur absolue.
    """
    correlations_triees = sorted(correlations, key=lambda c: abs(c["coefficient"]), reverse=True)
    return correlations_triees[:NOMBRE_CORRELATIONS_FORTES]


def _comprimer_colonnes(colonnes):
    """
    Compresse la liste des colonnes du profil Milestone #1 (même principe
    qu'ADR-10, trouvé nécessaire en test réel sur un dataset à 81 colonnes
    au total où le profil complet pesait 14 Ko à lui seul). Priorise les
    colonnes avec le taux de valeurs manquantes le plus élevé — les plus
    susceptibles de justifier un insight — et ne garde que les N premières.
    """
    colonnes_triees = sorted(colonnes, key=lambda c: c.get("taux_manquants") or 0, reverse=True)
    return colonnes_triees[:NOMBRE_COLONNES_DETAILLEES]


def _resumer_rapport_qualite(rapport_qualite):
    """Extrait du rapport Milestone #1 uniquement les champs agrégés utiles au LLM."""
    profil = rapport_qualite.get("profil", {})
    colonnes = profil.get("colonnes", [])
    correlations = profil.get("correlations", [])
    return {
        "jeu_de_donnees": rapport_qualite.get("jeu_de_donnees"),
        "score_global": rapport_qualite.get("score_global"),
        "scores_dimensions": rapport_qualite.get("scores_dimensions"),
        "taille": profil.get("taille"),
        "nombre_colonnes_total": len(colonnes),
        "colonnes_les_plus_pertinentes": _comprimer_colonnes(colonnes),
        "nombre_correlations_total": len(correlations),
        "correlations_les_plus_fortes": _comprimer_correlations(correlations),
    }


def construire_prompt(rapport_qualite, resultat_anomalies, resume_visualisations):
    """
    Construit le prompt à envoyer au LLM.

    - rapport_qualite : sortie de qualite_donnees.generer_rapport() (Milestone #1)
    - resultat_anomalies : sortie de anomalies.detecter() (Milestone #2) — compressée ici (ADR-10)
    - resume_visualisations : statistiques descriptives des visualisations
      produites par visualisations.py (ex. bornes d'histogramme, colonnes de
      la heatmap) — JAMAIS une image ou une chaîne base64

    Retourne (prompt_systeme, prompt_utilisateur), deux chaînes de
    caractères prêtes à être envoyées par client_llm.py.
    """
    donnees_fournies = {
        "rapport_qualite": _resumer_rapport_qualite(rapport_qualite),
        "resume_anomalies": _resumer_anomalies(resultat_anomalies),
        "resume_visualisations": resume_visualisations,
    }

    prompt_utilisateur = (
        "Voici les résultats déjà calculés pour ce jeu de données. "
        "Génère ta réponse en respectant STRICTEMENT ce contrat de sortie JSON "
        "(les valeurs ci-dessous sont des exemples de structure, pas des valeurs à recopier) :\n\n"
        f"{json.dumps(CONTRAT_SORTIE, ensure_ascii=False, indent=2)}\n\n"
        "Données fournies :\n\n"
        f"{json.dumps(donnees_fournies, ensure_ascii=False, indent=2, default=str)}"
    )

    return PROMPT_SYSTEME, prompt_utilisateur
