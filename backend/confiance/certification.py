"""
certification.py — Orchestrateur du Milestone #3 (Phase 3 : Confiance).

Assemble hachage.py + stockage_ipfs.py + qualite_donnees (Milestone #1,
consommé sans modification, ADR du Milestone #3 sur l'objectif) +
client_blockchain.py pour produire un certificat complet, ou vérifier un
fichier récupéré contre un certificat existant.

ADR-6 : jamais de certificat partiel. Si une étape échoue (upload IPFS,
transaction blockchain), la fonction retourne {"erreur": "..."} et
n'enregistre rien on-chain de partiel.
"""

import time
from datetime import datetime, timezone

from qualite_donnees import generer_rapport

from .client_blockchain import certifier as certifier_on_chain
from .client_blockchain import obtenir_certificat
from .client_blockchain import verifier_hash as verifier_hash_on_chain
from .hachage import calculer_hash_fichier, calculer_hash_metadonnees
from .stockage_ipfs import uploader_fichier

VERSION_PAR_DEFAUT = 1


def _construire_metadonnees(rapport_qualite, date_certification_iso):
    """Objet métadonnées structuré (ADR-2) : nom_fichier, score_global, scores_dimensions, date_certification."""
    return {
        "nom_fichier": rapport_qualite["jeu_de_donnees"],
        "score_global": rapport_qualite["score_global"],
        "scores_dimensions": rapport_qualite["scores_dimensions"],
        "date_certification": date_certification_iso,
    }


def certifier_dataset(chemin_fichier, owner_address, version=VERSION_PAR_DEFAUT, rapport_qualite=None):
    """
    Certifie un dataset de bout en bout : score qualité (Milestone #1),
    hash du fichier, upload IPFS, hash des métadonnées, enregistrement
    on-chain (Sepolia), puis relecture immédiate du certificat pour
    confirmer ce qui a réellement été enregistré (jamais une supposition).

    - chemin_fichier : chemin local du fichier CSV à certifier
    - owner_address : adresse déclarée du propriétaire du dataset (ADR-10) —
      transmise telle quelle au contrat, distincte du wallet qui signe la
      transaction (le wallet plateforme, voir client_blockchain.py)
    - version : numéro de version du dataset (uint16 côté contrat)
    - rapport_qualite : rapport déjà calculé par qualite_donnees.generer_rapport()
      (Milestone #1), pour éviter un recalcul si le pipeline l'a déjà produit
      en amont ; si None, il est recalculé ici à partir de chemin_fichier

    Retourne le certificat complet (champs on-chain relus + métadonnées +
    coût/temps par étape) en cas de succès, ou {"erreur": "..."} — jamais de
    certificat partiel (ADR-6).
    """
    mesures_temps = {}

    if rapport_qualite is None:
        debut = time.monotonic()
        rapport_qualite = generer_rapport(chemin_fichier)
        mesures_temps["qualite_donnees_secondes"] = round(time.monotonic() - debut, 3)

    debut = time.monotonic()
    dataset_hash = calculer_hash_fichier(chemin_fichier)
    mesures_temps["hachage_fichier_secondes"] = round(time.monotonic() - debut, 3)

    resultat_upload = uploader_fichier(chemin_fichier)
    if "erreur" in resultat_upload:
        return {"erreur": f"Échec de l'upload IPFS, certification annulée (ADR-6) : {resultat_upload['erreur']}"}
    mesures_temps["upload_ipfs_secondes"] = resultat_upload["temps_secondes"]

    date_certification_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # ISO 8601 UTC (ADR-11)
    objet_metadonnees = _construire_metadonnees(rapport_qualite, date_certification_iso)
    metadata_hash = calculer_hash_metadonnees(objet_metadonnees)

    resultat_chaine = certifier_on_chain(
        owner_address=owner_address,
        dataset_hash_hex=dataset_hash,
        ipfs_cid=resultat_upload["cid"],
        metadata_hash_hex=metadata_hash,
        version=version,
        quality_score=rapport_qualite["score_global"],
    )
    if "erreur" in resultat_chaine:
        return {
            "erreur": (
                "Échec de la certification on-chain, aucun certificat partiel enregistré (ADR-6) : "
                f"{resultat_chaine['erreur']}"
            )
        }
    mesures_temps["transaction_blockchain_secondes"] = resultat_chaine["temps_secondes"]

    # Relecture immédiate du certificat on-chain : ne jamais supposer que ce qui a été envoyé est
    # ce qui a été enregistré — on relit la source de vérité (même principe que la vérification des
    # critères d'acceptation par des mesures réelles tout au long du projet, cf. Milestone #2)
    certificat_releu = obtenir_certificat(resultat_chaine["dataset_id"])
    if "erreur" in certificat_releu:
        return {
            "erreur": (
                "Transaction confirmée mais relecture du certificat on-chain impossible : "
                f"{certificat_releu['erreur']}"
            )
        }

    return {
        **certificat_releu,  # dataset_id, owner, certifier, dataset_hash, ipfs_cid, metadata_hash, version, quality_score, timestamp
        "metadonnees": objet_metadonnees,
        "hash_transaction": resultat_chaine["hash_transaction"],
        "gas_utilise": resultat_chaine["gas_utilise"],
        "cout_eth": resultat_chaine["cout_eth"],
        "mesures_temps": mesures_temps,
        "temps_total_secondes": round(sum(mesures_temps.values()), 3),
    }


def verifier_dataset(chemin_fichier_recupere, dataset_id):
    """
    Vérifie qu'un fichier récupéré correspond au certificat enregistré
    on-chain pour ce datasetId (flux de vérification de la spec) : recalcule
    son SHA-256 puis le compare au datasetHash on-chain via verifyHash().

    Retourne {"resultat": "IDENTIQUE"|"ALTERE", "dataset_id":..., "hash_recalcule":...,
    "certificat": {...}} en cas de succès, ou {"erreur": "..."} si le
    certificat ou le fichier sont illisibles.
    """
    hash_recalcule = calculer_hash_fichier(chemin_fichier_recupere)

    resultat_verification = verifier_hash_on_chain(dataset_id, hash_recalcule)
    if "erreur" in resultat_verification:
        return {"erreur": resultat_verification["erreur"]}

    certificat = obtenir_certificat(dataset_id)
    if "erreur" in certificat:
        return {"erreur": certificat["erreur"]}

    return {
        "resultat": "IDENTIQUE" if resultat_verification["identique"] else "ALTERE",
        "dataset_id": dataset_id,
        "hash_recalcule": hash_recalcule,
        "certificat": certificat,
    }
