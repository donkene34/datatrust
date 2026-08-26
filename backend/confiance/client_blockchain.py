"""
client_blockchain.py — Intégration web3.py avec le smart contract
DatasetCertification.sol déployé sur Sepolia : certifier, lire et vérifier
un certificat de dataset.

ADR-5 : la clé privée du wallet (WALLET_PRIVATE_KEY) est lue depuis une
variable d'environnement, jamais codée en dur ni journalisée — la
conséquence d'une fuite est plus grave que pour une clé API (perte de
fonds/contrôle du wallet), donc traitée avec le même sérieux minimum que
GROQ_API_KEY, mais aucune valeur dérivée de la clé (ni la clé elle-même)
n'apparaît jamais dans un dict retourné ou un message d'erreur.

ADR-6 : en cas d'échec (réseau, transaction rejetée, contrat mal
configuré), ce module ne lève jamais d'exception pour les cas prévisibles
— il retourne un dict avec un champ "erreur" explicite, pour que
certification.py (orchestrateur) décide de ne rien certifier de partiel.

Variables d'environnement attendues :
- SEPOLIA_RPC_URL : URL du nœud RPC Sepolia (Alchemy, Infura, ou tout
  fournisseur compatible) — volontairement générique, pas de fournisseur
  imposé par ce module.
- WALLET_PRIVATE_KEY : clé privée du wallet plateforme (voir ADR-5, ADR-10)
  — doit correspondre à l'adresse authorizedCertifier fixée au déploiement
  du contrat, sinon certifyDataset() est rejeté côté contrat.
- CONTRACT_ADDRESS : adresse du contrat DatasetCertification déployé sur
  Sepolia.
"""

import json
import os
import time

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()  # même mécanisme que client_llm.py et stockage_ipfs.py — n'écrase jamais une variable déjà définie

DELAI_MAX_ATTENTE_RECU_SECONDES = 180  # temps d'attente max pour la confirmation d'une transaction sur Sepolia
CHEMIN_ABI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "contracts", "DatasetCertification_abi.json"
)


def _charger_abi():
    with open(CHEMIN_ABI, "r", encoding="utf-8") as flux:
        return json.load(flux)


def _configuration_absente_ou_invalide():
    """Retourne un message d'erreur si une variable d'environnement requise manque, sinon None."""
    if not os.environ.get("SEPOLIA_RPC_URL", "").strip():
        return "URL du nœud RPC Sepolia absente (variable d'environnement SEPOLIA_RPC_URL non définie)."
    if not os.environ.get("WALLET_PRIVATE_KEY", "").strip():
        return "Clé privée du wallet absente (variable d'environnement WALLET_PRIVATE_KEY non définie)."
    if not os.environ.get("CONTRACT_ADDRESS", "").strip():
        return "Adresse du contrat absente (variable d'environnement CONTRACT_ADDRESS non définie)."
    return None


def _construire_client():
    """
    Construit une instance Web3 connectée au nœud RPC configuré, le compte
    dérivé de la clé privée, et l'objet contrat (ABI + adresse).

    Retourne (w3, compte, contrat) en cas de succès, ou (None, None, None)
    avec un message d'erreur si la configuration est absente/invalide — la
    clé privée elle-même n'est jamais incluse dans le message d'erreur.
    """
    erreur_config = _configuration_absente_ou_invalide()
    if erreur_config:
        return None, None, None, erreur_config

    w3 = Web3(Web3.HTTPProvider(os.environ["SEPOLIA_RPC_URL"]))
    if not w3.is_connected():
        return None, None, None, "Connexion au nœud RPC Sepolia impossible (SEPOLIA_RPC_URL injoignable)."

    try:
        compte = w3.eth.account.from_key(os.environ["WALLET_PRIVATE_KEY"])
    except (ValueError, TypeError):
        return None, None, None, "Clé privée du wallet invalide (format incorrect)."

    try:
        adresse_contrat = w3.to_checksum_address(os.environ["CONTRACT_ADDRESS"])
        contrat = w3.eth.contract(address=adresse_contrat, abi=_charger_abi())
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        return None, None, None, f"Configuration du contrat invalide : {type(exc).__name__}"

    return w3, compte, contrat, None


def _hex_vers_bytes32(valeur_hex):
    """Convertit une chaîne hexadécimale (64 caractères, telle que produite par hachage.py) en bytes32."""
    valeur_nettoyee = valeur_hex[2:] if valeur_hex.startswith("0x") else valeur_hex
    return bytes.fromhex(valeur_nettoyee)


def certifier(owner_address, dataset_hash_hex, ipfs_cid, metadata_hash_hex, version, quality_score):
    """
    Appelle certifyDataset() sur le smart contract : construit, signe et
    envoie la transaction, attend sa confirmation, puis extrait le
    datasetId attribué depuis l'événement DatasetCertified (ADR-7).

    - owner_address : adresse déclarée du propriétaire du dataset (ADR-10)
    - dataset_hash_hex, metadata_hash_hex : chaînes hexadécimales (sortie de hachage.py)
    - quality_score : score qualité réel (ex. 99.61) — la conversion ×100
      en uint16 (ADR-3) est faite ici, pas dans qualite_donnees/ ni insights_ia/

    Retourne {"dataset_id": ..., "hash_transaction": ..., "gas_utilise": ...,
    "cout_wei": ..., "cout_eth": ..., "temps_secondes": ...} en cas de succès,
    ou {"erreur": "..."} en cas d'échec.
    """
    w3, compte, contrat, erreur_config = _construire_client()
    if erreur_config:
        return {"erreur": erreur_config}

    quality_score_uint16 = round(quality_score * 100)  # ADR-3

    debut = time.monotonic()
    try:
        adresse_owner = w3.to_checksum_address(owner_address)
        dataset_hash_bytes = _hex_vers_bytes32(dataset_hash_hex)
        metadata_hash_bytes = _hex_vers_bytes32(metadata_hash_hex)

        fonction = contrat.functions.certifyDataset(
            adresse_owner, dataset_hash_bytes, ipfs_cid, metadata_hash_bytes, version, quality_score_uint16
        )

        transaction = fonction.build_transaction(
            {
                "from": compte.address,
                "nonce": w3.eth.get_transaction_count(compte.address),
                "chainId": w3.eth.chain_id,
            }
        )
        transaction_signee = compte.sign_transaction(transaction)
        hash_transaction = w3.eth.send_raw_transaction(transaction_signee.raw_transaction)
        recu = w3.eth.wait_for_transaction_receipt(hash_transaction, timeout=DELAI_MAX_ATTENTE_RECU_SECONDES)
    except Exception as exc:
        # ex. transaction rejetée par le nœud (revert — dont "appelant non autorisé", cf. modifier
        # seulCertificateurAutorise du contrat —, gas insuffisant, timeout de confirmation) : le type
        # d'exception effectivement levé varie selon le fournisseur RPC (ValueError pour la plupart des
        # nœuds HTTP JSON-RPC, ContractLogicError si web3.py décode le motif de revert, TimeoutError si
        # la confirmation n'arrive pas) — capture volontairement large à cette frontière d'appel externe,
        # jamais d'exception non gérée, toujours une erreur explicite (ADR-6)
        return {"erreur": f"Transaction de certification rejetée : {type(exc).__name__}: {exc}"}
    duree = time.monotonic() - debut

    if recu.status != 1:
        return {"erreur": "Transaction de certification échouée on-chain (statut != 1)."}

    evenements = contrat.events.DatasetCertified().process_receipt(recu)
    if not evenements:
        return {"erreur": "Transaction confirmée mais événement DatasetCertified introuvable dans le reçu."}
    dataset_id = evenements[0]["args"]["datasetId"]

    prix_gas_effectif = recu.get("effectiveGasPrice", w3.eth.gas_price)
    cout_wei = recu.gasUsed * prix_gas_effectif

    return {
        "dataset_id": dataset_id,
        "hash_transaction": hash_transaction.hex(),
        "gas_utilise": recu.gasUsed,
        "cout_wei": cout_wei,
        "cout_eth": float(w3.from_wei(cout_wei, "ether")),
        "temps_secondes": round(duree, 3),
    }


def obtenir_certificat(dataset_id):
    """
    Lit le certificat associé à un datasetId via getCertificate() (lecture
    publique, gratuite — aucune transaction envoyée).

    Retourne un dict avec tous les champs du DatasetCertificate (owner,
    certifier, datasetHash et metadataHash reconvertis en hexadécimal,
    ipfsCID, version, qualityScore ramené à sa valeur réelle ÷100,
    timestamp), ou {"erreur": "..."} en cas d'échec.
    """
    w3, _compte, contrat, erreur_config = _construire_client()
    if erreur_config:
        return {"erreur": erreur_config}

    try:
        certificat = contrat.functions.getCertificate(dataset_id).call()
    except Exception as exc:
        # capture large pour la même raison que dans certifier() : le type d'exception varie selon
        # le fournisseur RPC pour un appel qui revert (ex. datasetId inexistant) (ADR-6)
        return {"erreur": f"Lecture du certificat impossible : {type(exc).__name__}: {exc}"}

    (owner, certifier_wallet, dataset_hash, ipfs_cid, metadata_hash, version, quality_score_uint16, timestamp) = (
        certificat
    )

    return {
        "dataset_id": dataset_id,
        "owner": owner,
        "certifier": certifier_wallet,
        "dataset_hash": dataset_hash.hex(),
        "ipfs_cid": ipfs_cid,
        "metadata_hash": metadata_hash.hex(),
        "version": version,
        "quality_score": quality_score_uint16 / 100,  # inverse de l'ADR-3
        "timestamp": timestamp,
    }


def verifier_hash(dataset_id, hash_recalcule_hex):
    """
    Appelle verifyHash() (lecture publique, gratuite) pour comparer un hash
    recalculé au datasetHash enregistré on-chain pour ce datasetId.

    Retourne {"identique": True/False} en cas de succès, ou {"erreur": "..."}
    en cas d'échec (ex. datasetId inexistant).
    """
    w3, _compte, contrat, erreur_config = _construire_client()
    if erreur_config:
        return {"erreur": erreur_config}

    try:
        hash_bytes = _hex_vers_bytes32(hash_recalcule_hex)
        identique = contrat.functions.verifyHash(dataset_id, hash_bytes).call()
    except Exception as exc:
        return {"erreur": f"Vérification du hash impossible : {type(exc).__name__}: {exc}"}

    return {"identique": identique}
