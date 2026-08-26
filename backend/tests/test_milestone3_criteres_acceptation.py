"""Tests boîte noire pour les 9 critères d'acceptation du Milestone #3
(docs/milestone_3_confiance.md). Seule l'API publique du package confiance est
utilisée (introspectée via inspect.signature) ; l'implémentation interne des
modules n'est pas consultée pour orienter les tests.

ATTENTION : chaque certification (confiance.certifier_dataset) envoie une
VRAIE transaction sur le réseau Sepolia (consomme du vrai ETH de test) et
incrémente datasetId sur le contrat. Les fixtures de conftest.py certifient
chaque dataset EXACTEMENT UNE FOIS par session pytest et réutilisent ce
résultat pour tous les critères concernés, plutôt que de répéter des
transactions. datasetId n'est jamais supposé fixe (ex. jamais 0/1) : on
utilise toujours l'identifiant réellement retourné par l'appel.

Aucune clé privée ni JWT Pinata n'est jamais affiché, journalisé ou écrit par
ces tests (critère 6) — seule l'adresse publique dérivée du wallet est
utilisée/affichée si besoin.
"""

import hashlib
import json
import os
import shutil
import tempfile

import pytest
import requests

from conftest import BACKEND_DIR

import confiance

CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
REPO_ROOT = BACKEND_DIR.parent


def _hash_independant(chemin_fichier):
    h = hashlib.sha256()
    with open(chemin_fichier, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


# Critère 1 : hachage.py calcule un SHA-256 identique à un calcul de référence
# indépendant (hashlib.sha256, hors du module) sur les 5 datasets
def test_critere_01_hash_fichier_identique_reference(dataset_paths):
    for nom, chemin in dataset_paths.items():
        hash_ref = _hash_independant(str(chemin))
        hash_module = confiance.hachage.calculer_hash_fichier(str(chemin))
        assert len(hash_module) == 64, f"{nom}: hash de longueur inattendue ({len(hash_module)})"
        assert hash_module == hash_ref, f"{nom}: hash module != hash de référence indépendant"


# Critère 2 : stockage_ipfs.py upload un fichier vers IPFS et retourne un CID valide ;
# télécharger via ce CID puis recalculer son hash donne le même datasetHash
def test_critere_02_ipfs_upload_download_hash_identique(certificats, dataset_paths):
    for nom, cert in certificats.items():
        cid = cert["ipfs_cid"]
        assert cid, f"{nom}: CID vide"
        with tempfile.TemporaryDirectory() as tmpdir:
            chemin_telecharge = os.path.join(tmpdir, "telecharge")
            confiance.stockage_ipfs.telecharger_fichier(cid, chemin_telecharge)
            hash_telecharge = confiance.hachage.calculer_hash_fichier(chemin_telecharge)
            assert hash_telecharge == cert["dataset_hash"], (
                f"{nom}: hash du fichier téléchargé via CID {cid} != datasetHash enregistré"
            )


# Critère 3 : le smart contract se déploie sans erreur sur Sepolia et est
# vérifiable manuellement sur Etherscan (ADR-8)
def test_critere_03_contrat_deploye_et_verifie_etherscan():
    from web3 import Web3

    rpc = os.environ.get("SEPOLIA_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))
    assert w3.is_connected(), "connexion au RPC Sepolia impossible"

    code = w3.eth.get_code(Web3.to_checksum_address(CONTRACT_ADDRESS))
    assert len(code) > 0, f"aucun bytecode déployé à l'adresse {CONTRACT_ADDRESS}"

    url = f"https://sepolia.etherscan.io/address/{CONTRACT_ADDRESS}#code"
    try:
        reponse = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; test-script/1.0)"})
        html = reponse.text
    except requests.RequestException as exc:
        pytest.skip(f"Etherscan injoignable depuis cet environnement ({exc}) ; bytecode déployé confirmé au minimum")
        return

    verifie = ("Exact Match" in html) or ("Similar Match" in html) or ("Contract Source Code Verified" in html)
    assert verifie, "aucun marqueur de vérification trouvé sur la page Etherscan du contrat"


# Critère 4 : certifyDataset() enregistre un certificat lisible via getCertificate(),
# avec owner = adresse déclarée, certifier = msg.sender, timestamp = block.timestamp
def test_critere_04_certificat_champs_corrects(certificats, adresse_wallet_plateforme):
    owners_vus = set()
    for nom, cert in certificats.items():
        relu = confiance.client_blockchain.obtenir_certificat(cert["dataset_id"])
        assert "erreur" not in relu, f"{nom}: relecture du certificat {cert['dataset_id']} échouée : {relu}"

        assert relu["certifier"] == adresse_wallet_plateforme, (
            f"{nom}: certifier={relu['certifier']} != wallet plateforme {adresse_wallet_plateforme}"
        )
        assert relu["owner"] == cert["owner"], f"{nom}: owner relu différent de celui déclaré à l'appel"
        assert relu["dataset_hash"] == cert["dataset_hash"]
        assert relu["ipfs_cid"] == cert["ipfs_cid"]
        assert isinstance(relu["timestamp"], int) and relu["timestamp"] > 1_700_000_000, (
            f"{nom}: timestamp on-chain invalide ou absent : {relu['timestamp']}"
        )
        owners_vus.add(relu["owner"])

    # ADR-10 : owner (déclaré) et certifier (msg.sender) doivent être des champs
    # distincts — vérifié en s'assurant qu'au moins un owner diffère du certifier
    assert owners_vus - {adresse_wallet_plateforme}, (
        "aucun dataset testé n'a un owner différent du certifier : la distinction ADR-10 "
        "n'est pas vérifiée (voir OWNER_ADDRESS_DISTINCT_TEST dans conftest.py)"
    )


# Critère 5 : verifyHash() retourne true pour le hash correct et false pour un
# hash modifié (fichier délibérément altéré)
def test_critere_05_verifyhash_true_false(certificats, dataset_paths):
    nom, cert = next(iter(certificats.items()))
    chemin_original = dataset_paths[nom]

    hash_correct = confiance.hachage.calculer_hash_fichier(str(chemin_original))
    resultat_correct = confiance.client_blockchain.verifier_hash(cert["dataset_id"], hash_correct)
    assert resultat_correct.get("identique") is True, f"{nom}: verifyHash(bon hash) devrait être True, obtenu {resultat_correct}"

    with tempfile.TemporaryDirectory() as tmpdir:
        chemin_altere = os.path.join(tmpdir, "altere" + chemin_original.suffix)
        shutil.copyfile(str(chemin_original), chemin_altere)
        with open(chemin_altere, "ab") as f:
            f.write(b"\ndonnee alteree pour test critere 5\n")

        hash_altere = confiance.hachage.calculer_hash_fichier(chemin_altere)
        assert hash_altere != hash_correct
        resultat_altere = confiance.client_blockchain.verifier_hash(cert["dataset_id"], hash_altere)
        assert resultat_altere.get("identique") is False, (
            f"{nom}: verifyHash(hash altéré) devrait être False, obtenu {resultat_altere}"
        )


# Critère 6 : aucune clé privée n'apparaît dans les logs, le JSON de sortie, ou un fichier commité
def test_critere_06_pas_de_cle_privee_dans_sortie(certificats_bruts, capsys):
    cle_privee = os.environ.get("WALLET_PRIVATE_KEY")
    jwt_pinata = os.environ.get("PINATA_JWT")
    assert cle_privee and jwt_pinata, "variables d'environnement manquantes pour ce test"

    serialise = json.dumps(certificats_bruts, ensure_ascii=False, default=str)
    assert cle_privee not in serialise, "la clé privée du wallet apparaît dans la sortie de certification"
    assert jwt_pinata not in serialise, "le JWT Pinata apparaît dans la sortie de certification"

    sortie = capsys.readouterr()
    assert cle_privee not in sortie.out and cle_privee not in sortie.err
    assert jwt_pinata not in sortie.out and jwt_pinata not in sortie.err

    # Aucun fichier commité ne doit contenir ces secrets (le seul endroit légitime est .env, gitignoré)
    import subprocess

    suivis = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for chemin_relatif in suivis:
        chemin_abs = REPO_ROOT / chemin_relatif
        if not chemin_abs.is_file():
            continue
        try:
            contenu = chemin_abs.read_text(encoding="utf-8", errors="ignore")
        except (UnicodeDecodeError, PermissionError):
            continue
        assert cle_privee not in contenu, f"clé privée trouvée dans un fichier COMMITÉ : {chemin_relatif}"
        assert jwt_pinata not in contenu, f"JWT Pinata trouvé dans un fichier COMMITÉ : {chemin_relatif}"


# Critère 7 : le pipeline complet (certification puis vérification) fonctionne
# de bout en bout sur au moins 3 des 5 datasets
def test_critere_07_pipeline_bout_en_bout_au_moins_3_datasets(certificats):
    reussites = {}
    for nom, cert in certificats.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            chemin_telecharge = os.path.join(tmpdir, "telecharge")
            confiance.stockage_ipfs.telecharger_fichier(cert["ipfs_cid"], chemin_telecharge)
            resultat = confiance.verifier_dataset(chemin_telecharge, cert["dataset_id"])
            reussites[nom] = resultat.get("resultat") == "IDENTIQUE"

    nb_reussites = sum(reussites.values())
    assert nb_reussites >= 3, (
        f"seulement {nb_reussites}/5 datasets ont réussi le pipeline complet bout en bout : {reussites}"
    )


# Critère 8 : metadataHash est reproductible (même objet Python, appels séparés,
# sérialisation canonique ADR-11)
def test_critere_08_metadata_hash_reproductible():
    objet = {
        "nom_fichier": "exemple.csv",
        "score_global": 87.65,
        "scores_dimensions": {"completude": {"score": 100.0, "statut": "evalue"}},
        "date_certification": "2026-08-26T18:00:00Z",
    }
    h1 = confiance.hachage.calculer_hash_metadonnees(objet)
    h2 = confiance.hachage.calculer_hash_metadonnees(dict(objet))
    objet_cles_reordonnees = {
        "date_certification": objet["date_certification"],
        "scores_dimensions": objet["scores_dimensions"],
        "nom_fichier": objet["nom_fichier"],
        "score_global": objet["score_global"],
    }
    h3 = confiance.hachage.calculer_hash_metadonnees(objet_cles_reordonnees)

    assert len(h1) == 64
    assert h1 == h2, "deux appels avec le même objet donnent des hash différents"
    assert h1 == h3, "l'ordre des clés dans l'objet Python affecte le hash (sérialisation non canonique, ADR-11)"


# Critère 9 : mesure réelle de performance sur les 5 datasets (jamais supposée)
def test_critere_09_mesures_performance_5_datasets(certificats_bruts, dataset_paths):
    try:
        prix_eth_usd = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=15
        ).json()["ethereum"]["usd"]
    except Exception:  # noqa: BLE001
        prix_eth_usd = None

    lignes = []
    for nom, chemin in dataset_paths.items():
        taille_mo = os.path.getsize(str(chemin)) / (1024 * 1024)
        resultat = certificats_bruts.get(nom)

        if isinstance(resultat, dict) and "erreur" not in resultat:
            m = resultat["mesures_temps"]
            cout_fiat = f"${resultat['cout_eth'] * prix_eth_usd:.4f}" if prix_eth_usd else "n/a"
            lignes.append({
                "dataset": nom,
                "taille_mo": round(taille_mo, 2),
                "temps_hash_s": m["hachage_fichier_secondes"],
                "temps_upload_ipfs_s": m["upload_ipfs_secondes"],
                "cid": resultat["ipfs_cid"],
                "temps_transaction_s": m["transaction_blockchain_secondes"],
                "gas_utilise": resultat["gas_utilise"],
                "cout_eth": resultat["cout_eth"],
                "cout_fiat_usd": cout_fiat,
                "temps_total_s": resultat["temps_total_secondes"],
                "statut": "REUSSI",
            })
        else:
            detail_erreur = resultat.get("erreur") if isinstance(resultat, dict) else str(resultat)
            lignes.append({
                "dataset": nom,
                "taille_mo": round(taille_mo, 2),
                "temps_hash_s": round(_temps_hash_seul(str(chemin)), 3),
                "temps_upload_ipfs_s": None,
                "cid": None,
                "temps_transaction_s": None,
                "gas_utilise": None,
                "cout_eth": None,
                "cout_fiat_usd": None,
                "temps_total_s": None,
                "statut": f"ECHEC: {detail_erreur}",
            })

    entete = f"{'Dataset':38} {'Taille(Mo)':>10} {'Hash(s)':>8} {'Upload(s)':>10} {'Tx(s)':>8} {'Gas':>9} {'Cout(ETH)':>12} {'Cout':>10} {'Total(s)':>9} {'Statut'}"
    print("\n--- Critère 9 : mesures de performance réelles (5 datasets) ---")
    print(entete)
    for l in lignes:
        print(
            f"{l['dataset']:38} {l['taille_mo']:>10} {str(l['temps_hash_s']):>8} "
            f"{str(l['temps_upload_ipfs_s']):>10} {str(l['temps_transaction_s']):>8} "
            f"{str(l['gas_utilise']):>9} {str(l['cout_eth']):>12} {str(l['cout_fiat_usd']):>10} "
            f"{str(l['temps_total_s']):>9} {l['statut']}"
        )

    for l in lignes:
        assert l["taille_mo"] > 0, f"{l['dataset']}: taille de fichier nulle ou absente"
        assert l["temps_hash_s"] is not None and l["temps_hash_s"] >= 0

    nb_reussis = sum(1 for l in lignes if l["statut"] == "REUSSI")
    assert nb_reussis >= 3, f"moins de 3/5 datasets ont une mesure de performance complète : {nb_reussis}/5"

    for l in lignes:
        if l["statut"] == "REUSSI":
            assert l["cid"], f"{l['dataset']}: CID manquant"
            assert l["temps_upload_ipfs_s"] > 0
            assert l["temps_transaction_s"] > 0
            assert l["gas_utilise"] > 0
            assert l["cout_eth"] > 0
            assert l["temps_total_s"] > 0


def _temps_hash_seul(chemin_fichier):
    import time
    t0 = time.time()
    confiance.hachage.calculer_hash_fichier(chemin_fichier)
    return time.time() - t0
