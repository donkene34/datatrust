// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title DatasetCertification
/// @notice Contrat de certification de datasets pour la plateforme Data Trust & Insights (Milestone #3).
/// Documentation et commentaires en français (ADR-9) ; conventions de nommage Solidity/Web3 en anglais.
contract DatasetCertification {

    // Structure d'un certificat on-chain (voir spec Milestone #3, ADR-1 à ADR-4, ADR-10)
    struct DatasetCertificate {
        address owner;          // propriétaire DÉCLARÉ du dataset (fourni par l'appelant, pas forcément msg.sender) — ADR-10
        address certifier;      // wallet ayant réellement soumis la transaction (msg.sender) — ADR-10
        bytes32 datasetHash;    // SHA-256 du contenu brut du fichier — ADR-1
        string  ipfsCID;        // identifiant IPFS permettant de récupérer le fichier
        bytes32 metadataHash;   // SHA-256 de la sérialisation JSON canonique des métadonnées — ADR-2, ADR-11
        uint16  version;        // numéro de version du dataset
        uint16  qualityScore;   // score qualité × 100 (ex. 9961 = 99.61) — ADR-3
        uint256 timestamp;      // block.timestamp, fixé par le contrat, jamais transmis par l'appelant — ADR-4
    }

    // datasetId : identifiant numérique auto-incrémenté (ADR-7) — le hash reste la preuve d'identité du contenu,
    // le datasetId n'est qu'un index pratique
    uint256 private nextDatasetId;

    // Stockage des certificats, indexés par datasetId
    mapping(uint256 => DatasetCertificate) private certificates;

    // Adresse du wallet plateforme autorisé à certifier (ADR-10 : wallet unique pour le MVP).
    // Fixée une fois pour toutes au déploiement — pas de fonction de transfert dans ce MVP,
    // un changement de wallet nécessiterait un redéploiement (acceptable au vu du périmètre figé).
    address public immutable authorizedCertifier;

    // Émis à chaque certification réussie — permet d'indexer les certificats hors-chaîne (ex. frontend, Phase 4)
    // sans avoir à interroger chaque datasetId un par un.
    event DatasetCertified(
        uint256 indexed datasetId,
        address indexed owner,
        address indexed certifier,
        bytes32 datasetHash,
        string ipfsCID,
        uint256 timestamp
    );

    // Restreint certifyDataset() au wallet plateforme autorisé (ADR-10) — empêche n'importe quelle
    // adresse d'émettre de faux certificats sur ce contrat, ce qui casserait la confiance que le
    // projet cherche justement à établir ("Data Trust").
    modifier seulCertificateurAutorise() {
        require(msg.sender == authorizedCertifier, "DatasetCertification: appelant non autorise a certifier");
        _;
    }

    /// @dev authorizedCertifier est fixé au déploiement à l'adresse du wallet plateforme (ADR-10).
    constructor(address walletPlateforme) {
        require(walletPlateforme != address(0), "DatasetCertification: adresse du wallet plateforme invalide");
        authorizedCertifier = walletPlateforme;
    }

    /// @notice Enregistre un nouveau certificat de dataset.
    /// @dev owner = ownerAddress (déclaré, pas forcément l'appelant) ; certifier = msg.sender (ADR-10) ;
    /// timestamp = block.timestamp, jamais transmis par l'appelant (ADR-4). Retourne le datasetId attribué (ADR-7).
    function certifyDataset(
        address ownerAddress,
        bytes32 datasetHash,
        string calldata ipfsCID,
        bytes32 metadataHash,
        uint16 version,
        uint16 qualityScore
    ) external seulCertificateurAutorise returns (uint256 datasetId) {
        require(ownerAddress != address(0), "DatasetCertification: adresse owner invalide");
        require(datasetHash != bytes32(0), "DatasetCertification: datasetHash vide");
        require(bytes(ipfsCID).length > 0, "DatasetCertification: ipfsCID vide");

        datasetId = nextDatasetId;
        nextDatasetId += 1;

        certificates[datasetId] = DatasetCertificate({
            owner: ownerAddress,
            certifier: msg.sender,
            datasetHash: datasetHash,
            ipfsCID: ipfsCID,
            metadataHash: metadataHash,
            version: version,
            qualityScore: qualityScore,
            timestamp: block.timestamp
        });

        emit DatasetCertified(datasetId, ownerAddress, msg.sender, datasetHash, ipfsCID, block.timestamp);
    }

    /// @notice Retourne le certificat associé à un datasetId (lecture publique, gratuite).
    function getCertificate(uint256 datasetId) external view returns (DatasetCertificate memory) {
        require(datasetId < nextDatasetId, "DatasetCertification: datasetId inexistant");
        return certificates[datasetId];
    }

    /// @notice Compare un hash recalculé au datasetHash enregistré on-chain (sans transaction payante).
    /// @return true si le hash correspond exactement (fichier intact), false sinon (fichier altéré).
    function verifyHash(uint256 datasetId, bytes32 recomputedHash) external view returns (bool) {
        require(datasetId < nextDatasetId, "DatasetCertification: datasetId inexistant");
        return certificates[datasetId].datasetHash == recomputedHash;
    }

    /// @notice Nombre total de certificats enregistrés (utile pour parcourir tous les datasetId côté backend/frontend).
    function totalCertificates() external view returns (uint256) {
        return nextDatasetId;
    }
}
