"""
client_llm.py — Appel à l'API Groq (modèle de langage texte), pour
transformer le prompt structuré (invite.py) en résumé/insights/recommandations.

ADR-4 : la clé API est lue depuis la variable d'environnement GROQ_API_KEY,
jamais codée en dur ni journalisée. Pour que cette variable soit disponible
quelle que soit l'interface utilisée (terminal, extension VS Code, Claude
Code CLI...) sans dépendre de l'héritage d'environnement du shell, un
fichier .env (à la racine ou dans backend/, ignoré par git) est chargé
automatiquement au démarrage via python-dotenv — sans jamais écraser une
variable déjà définie par le système.
ADR-5 : si l'appel échoue (clé absente, erreur réseau, quota dépassé,
réponse non conforme au contrat), la fonction ne lève jamais d'exception :
elle retourne un dict avec un champ "erreur" explicite, pour que le reste
du pipeline (moteur.py) reste disponible même sans LLM.
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()  # cherche un .env en remontant depuis le dossier courant ;
                # n'écrase jamais une variable d'environnement déjà définie

URL_API_GROQ = "https://api.groq.com/openai/v1/chat/completions"
# "llama-3.3-70b-versatile" (choix initial) a été déprécié par Groq le
# 16/08/2026 — découvert en test réel (erreur "model_not_found" de l'API),
# pas anticipé dans la spec. Remplacé par le modèle recommandé par Groq à
# la place (voir console.groq.com/docs/deprecations). À surveiller : les
# modèles Groq évoluent régulièrement, cette constante pourra devoir être
# mise à jour de nouveau.
MODELE_PAR_DEFAUT = "openai/gpt-oss-120b"
DELAI_MAX_SECONDES = 30
MAX_TOKENS_REPONSE = 3000  # openai/gpt-oss-120b est un modèle "à raisonnement" (champ
                            # "reasoning" séparé de "content" dans la réponse Groq) ; max_tokens
                            # semble plafonner raisonnement + contenu visible ENSEMBLE. À 1500,
                            # trouvé en test réel : le JSON produit était valide mais incomplet
                            # (recommandations manquant) sur le dataset le plus riche (énergie) —
                            # pas une erreur de parsing, juste pas assez de budget restant après
                            # le raisonnement caché. Remonté à 3000, qui laisse encore une bonne
                            # marge sous la limite de 8000 TPM du tier gratuit même sur le prompt
                            # le plus gros mesuré (~4000 tokens, dataset immobilier).


def _cle_api_absente_ou_invalide(cle_api):
    return not cle_api or not cle_api.strip()


def appeler_llm(prompt_systeme, prompt_utilisateur, modele=MODELE_PAR_DEFAUT):
    """
    Appelle l'API Groq avec le prompt fourni (voir invite.py) et retourne la
    réponse JSON déjà parsée du LLM (le contrat resume/insights/recommandations),
    ou un dict {"erreur": "..."} en cas d'échec — ne lève jamais d'exception.

    La clé API n'apparaît jamais dans la valeur de retour ni dans un message
    d'erreur : en cas d'échec HTTP, seul le code de statut et un message
    générique sont inclus, jamais les en-têtes de la requête ni la clé elle-même.
    """
    cle_api = os.environ.get("GROQ_API_KEY")

    if _cle_api_absente_ou_invalide(cle_api):
        return {"erreur": "Clé API Groq absente (variable d'environnement GROQ_API_KEY non définie)."}

    en_tetes = {
        "Authorization": f"Bearer {cle_api}",
        "Content-Type": "application/json",
    }
    corps = {
        "model": modele,
        "messages": [
            {"role": "system", "content": prompt_systeme},
            {"role": "user", "content": prompt_utilisateur},
        ],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS_REPONSE,
        "response_format": {"type": "json_object"},
    }

    try:
        reponse = requests.post(URL_API_GROQ, headers=en_tetes, json=corps, timeout=DELAI_MAX_SECONDES)
    except requests.exceptions.RequestException as exc:
        return {"erreur": f"Erreur réseau lors de l'appel à l'API Groq : {type(exc).__name__}"}

    if reponse.status_code == 401:
        return {"erreur": "Clé API Groq invalide ou refusée par le serveur (HTTP 401)."}
    if reponse.status_code == 429:
        return {"erreur": "Quota de l'API Groq dépassé (HTTP 429)."}
    if reponse.status_code >= 400:
        return {"erreur": f"Erreur de l'API Groq (HTTP {reponse.status_code})."}

    try:
        corps_reponse = reponse.json()
        contenu = corps_reponse["choices"][0]["message"]["content"]
        resultat = json.loads(contenu)
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return {"erreur": "Réponse du LLM non conforme au format JSON attendu."}

    if not _respecte_le_contrat(resultat):
        return {"erreur": "Réponse du LLM ne respecte pas le contrat de sortie attendu (resume/insights/recommandations)."}

    return resultat


def _respecte_le_contrat(resultat):
    """
    Vérifie que la réponse du LLM respecte le contrat de sortie (ADR-7) :
    "resume" (texte non vide), "insights" (liste) et "recommandations"
    (liste, au moins 1 élément — champ obligatoire, contrairement au nombre
    d'insights qui peut varier selon les données).

    Trouvé en test réel : un modèle a déjà omis complètement la clé
    "recommandations" (pas même une liste vide) malgré le contrat fourni
    dans le prompt. Sans cette vérification, une réponse non conforme
    aurait été acceptée telle quelle au lieu de dégrader proprement
    (ADR-5) — le contrat doit être imposé côté code, pas seulement
    espéré du prompt.
    """
    if not isinstance(resultat, dict):
        return False
    if not resultat.get("resume") or not isinstance(resultat.get("resume"), str):
        return False
    if not isinstance(resultat.get("insights"), list):
        return False
    recommandations = resultat.get("recommandations")
    if not isinstance(recommandations, list) or len(recommandations) < 1:
        return False
    return True
