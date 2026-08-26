"""
stockage_ipfs.py — Upload et récupération de fichiers via IPFS (Pinata).

ADR-6 : en cas d'échec (réseau, authentification, quota), ce module ne lève
jamais d'exception pour les cas prévisibles — il retourne un dict avec un
champ "erreur" explicite, pour que certification.py (orchestrateur) décide
de ne rien certifier de partiel plutôt que de laisser une exception remonter
de façon incontrôlée.

Jeton API : lu depuis la variable d'environnement PINATA_JWT (jeton JWT
Pinata), jamais codé en dur ni journalisé — même principe que GROQ_API_KEY
(Milestone #2, ADR-4) et WALLET_PRIVATE_KEY (ADR-5).
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()  # même mécanisme que client_llm.py (Milestone #2) — n'écrase jamais une variable déjà définie

URL_UPLOAD_PINATA = "https://api.pinata.cloud/pinning/pinFileToIPFS"
URL_GATEWAY_IPFS = "https://gateway.pinata.cloud/ipfs/"  # passerelle publique pour récupérer un fichier via son CID
DELAI_MAX_SECONDES = 600  # Bug corrigé : à 120s, l'upload du dataset énergie (~127 Mo) échouait
                           # systématiquement (3/3 tentatives, ConnectionError après ~140s) en test réel
                           # (Claude Code, Milestone #3). La documentation Pinata confirme que /pinFileToIPFS
                           # reste utilisable au-delà de 100 Mo (pas de limite serveur bloquante à cette
                           # taille) — le timeout client était la cause la plus probable. Remonté à 600s :
                           # une certification est une opération ponctuelle, pas un appel interactif
                           # sensible à la latence, donc un délai plus généreux ne coûte rien.
TAILLE_BLOC_TELECHARGEMENT_OCTETS = 1024 * 1024  # 1 Mo par bloc, en streaming, pour ne pas tout charger en mémoire


def _jeton_absent_ou_invalide(jeton):
    return not jeton or not jeton.strip()


def uploader_fichier(chemin_fichier):
    """
    Upload un fichier vers IPFS via Pinata (pinning) et retourne son CID.

    Retourne {"cid": "...", "taille_octets": ..., "temps_secondes": ...}
    en cas de succès, ou {"erreur": "..."} en cas d'échec — ne lève jamais
    d'exception pour les cas prévisibles (ADR-6).
    """
    jeton = os.environ.get("PINATA_JWT")
    if _jeton_absent_ou_invalide(jeton):
        return {"erreur": "Jeton API Pinata absent (variable d'environnement PINATA_JWT non définie)."}

    if not os.path.isfile(chemin_fichier):
        return {"erreur": f"Fichier introuvable : {chemin_fichier}"}

    en_tetes = {"Authorization": f"Bearer {jeton}"}
    nom_fichier = os.path.basename(chemin_fichier)
    taille_octets = os.path.getsize(chemin_fichier)

    debut = time.monotonic()
    try:
        with open(chemin_fichier, "rb") as flux:
            fichiers = {"file": (nom_fichier, flux)}
            reponse = requests.post(
                URL_UPLOAD_PINATA,
                headers=en_tetes,
                files=fichiers,
                timeout=DELAI_MAX_SECONDES,
            )
    except requests.exceptions.RequestException as exc:
        return {"erreur": f"Erreur réseau lors de l'upload vers Pinata : {type(exc).__name__}"}
    duree = time.monotonic() - debut

    if reponse.status_code == 401:
        return {"erreur": "Jeton API Pinata invalide ou refusé par le serveur (HTTP 401)."}
    if reponse.status_code >= 400:
        return {"erreur": f"Erreur de l'API Pinata (HTTP {reponse.status_code})."}

    try:
        corps_reponse = reponse.json()
        cid = corps_reponse["IpfsHash"]
    except (KeyError, ValueError):
        return {"erreur": "Réponse de l'API Pinata non conforme au format attendu (CID absent)."}

    return {"cid": cid, "taille_octets": taille_octets, "temps_secondes": round(duree, 3)}


def telecharger_fichier(cid, chemin_destination):
    """
    Récupère un fichier depuis IPFS via son CID (passerelle publique Pinata)
    et l'écrit à chemin_destination, en streaming par blocs pour rester
    efficace en mémoire sur de gros fichiers.

    Retourne {"chemin_destination": "...", "taille_octets": ..., "temps_secondes": ...}
    en cas de succès, ou {"erreur": "..."} en cas d'échec.
    """
    url = URL_GATEWAY_IPFS + cid

    debut = time.monotonic()
    try:
        with requests.get(url, stream=True, timeout=DELAI_MAX_SECONDES) as reponse:
            if reponse.status_code >= 400:
                return {
                    "erreur": f"Erreur lors de la récupération IPFS (HTTP {reponse.status_code}) pour le CID {cid}."
                }
            with open(chemin_destination, "wb") as flux_sortie:
                for bloc in reponse.iter_content(chunk_size=TAILLE_BLOC_TELECHARGEMENT_OCTETS):
                    if bloc:
                        flux_sortie.write(bloc)
    except requests.exceptions.RequestException as exc:
        return {"erreur": f"Erreur réseau lors de la récupération IPFS : {type(exc).__name__}"}
    duree = time.monotonic() - debut

    taille_octets = os.path.getsize(chemin_destination)
    return {
        "chemin_destination": chemin_destination,
        "taille_octets": taille_octets,
        "temps_secondes": round(duree, 3),
    }
