"""
moteur.py — Assemble le pipeline complet du Milestone #2 : artefact
analytique + détection d'anomalies + visualisations + appel LLM, combinés
avec le rapport qualité du Milestone #1 (inchangé) dans un JSON final.

ADR-5 : un échec de l'appel LLM ne fait jamais planter le moteur — les
sections qualité/anomalies/visualisations restent disponibles même si
"insights_ia" contient {"erreur": "..."}.

Critère d'acceptation 12 : le pipeline mesure et journalise explicitement
(jamais suppose) le temps de chargement du CSV, le temps de construction de
l'artefact analytique, l'usage mémoire, le temps d'exécution d'Isolation
Forest, et le temps de génération des visualisations — voir le bloc
"performance" du JSON retourné.
"""

import time

import psutil

from qualite_donnees import generer_rapport

from .anomalies import detecter as detecter_anomalies
from .artefact_analytique import construire as construire_artefact
from .client_llm import appeler_llm
from .invite import construire_prompt
from .visualisations import generer as generer_visualisations


def _memoire_maximale_mo():
    """
    Usage mémoire du processus Python, en mégaoctets, mesuré via psutil.

    Corrige un bug de portabilité trouvé par Claude Code lors des tests du
    Milestone #2 : la première version utilisait le module standard
    `resource`, qui n'existe que sur Unix — son simple import faisait
    planter l'import de tout `insights_ia` sous Windows (la machine de
    développement du projet). psutil fonctionne de façon identique sur
    Windows, macOS et Linux.

    Sous Windows, psutil expose un vrai pic (`peak_wset`, le working set
    maximal atteint). Sous Unix, cette information n'est pas exposée par
    psutil de la même façon : on retombe alors sur la RSS courante au
    moment de l'appel — une bonne approximation du pic pour ce pipeline,
    car l'allocateur mémoire de Python ne rend généralement pas la mémoire
    à l'OS immédiatement après un pic d'utilisation. Limite à documenter
    honnêtement : ce n'est donc pas un pic instrumenté à chaque étape, ni
    strictement comparable entre Windows et Unix.
    """
    processus = psutil.Process()
    info = processus.memory_info()
    octets = getattr(info, "peak_wset", None) or info.rss
    return round(octets / (1024 * 1024), 2)


def generer_rapport_intelligence(chemin_fichier, modele_llm=None, rapport_qualite=None):
    """
    Point d'entrée principal du Milestone #2 : construit le JSON complet
    combinant qualité (Milestone #1, inchangé), anomalies, visualisations
    et insights IA, pour le fichier CSV donné.

    Retourne :
    {
        "qualite": {...},              # qualite_donnees.generer_rapport(), inchangé
        "anomalies": {...},            # sortie complète de anomalies.detecter() (ADR-9)
        "visualisations": {...},       # sortie complète de visualisations.generer()
        "insights_ia": {...} | {"erreur": "..."},
        "performance": {
            "temps_chargement_secondes": float,
            "temps_construction_artefact_secondes": float,
            "temps_anomalies_secondes": float,
            "temps_visualisations_secondes": float,
            "memoire_maximale_mo": float,
        },
    }

    Ne lève jamais d'exception à cause d'un échec du LLM (ADR-5) : dans ce
    cas, "insights_ia" contient {"erreur": "..."} et le reste du JSON reste
    complet et correct (critère 7).

    Paramètre rapport_qualite (ajouté au Milestone #4, ADR-12, API) :
    optionnel, None par défaut — dans ce cas le comportement est strictement
    identique à celui validé au Milestone #2 (rapport qualité recalculé en
    interne). Si un rapport déjà calculé par qualite_donnees.generer_rapport()
    sur ce MÊME fichier est fourni, il est réutilisé tel quel et l'appel
    interne à generer_rapport() est sauté, pour éviter un recalcul coûteux
    quand l'appelant (l'API Phase 4a) a déjà ce rapport sous la main. La
    vérification que ce rapport correspond bien à chemin_fichier est de la
    responsabilité de l'appelant (l'API vérifie un dataset_hash avant
    d'appeler cette fonction, voir Milestone #4) — ce module ne le revérifie
    pas lui-même, il fait confiance à ce qu'on lui fournit, comme le reste
    du pipeline (voir "jamais le dataset brut" dans invite.py). construire_artefact()
    continue de relire le fichier séparément dans tous les cas : il construit
    une structure différente (matrice de features pour les anomalies), pas
    remplaçable par le rapport qualité.
    """
    if rapport_qualite is None:
        rapport_qualite = generer_rapport(chemin_fichier)

    artefact = construire_artefact(chemin_fichier)
    temps_secondes_artefact = artefact["temps_secondes"]

    resultat_anomalies = detecter_anomalies(artefact)

    debut_visualisations = time.perf_counter()
    resultat_visualisations = generer_visualisations(artefact, rapport_qualite["profil"])
    temps_visualisations = time.perf_counter() - debut_visualisations

    kwargs_llm = {"modele": modele_llm} if modele_llm else {}
    prompt_systeme, prompt_utilisateur = construire_prompt(
        rapport_qualite, resultat_anomalies, resultat_visualisations["resume_pour_prompt"]
    )
    insights_ia = appeler_llm(prompt_systeme, prompt_utilisateur, **kwargs_llm)

    return {
        "qualite": rapport_qualite,
        "anomalies": resultat_anomalies,
        "visualisations": resultat_visualisations,
        "insights_ia": insights_ia,
        "performance": {
            "temps_chargement_secondes": temps_secondes_artefact["chargement"],
            "temps_construction_artefact_secondes": temps_secondes_artefact["transformation"],
            "temps_anomalies_secondes": resultat_anomalies["temps_execution_secondes"],
            "temps_visualisations_secondes": round(temps_visualisations, 4),
            "memoire_maximale_mo": _memoire_maximale_mo(),
        },
    }
