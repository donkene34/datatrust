# Milestone #3 — Phase 3 : Confiance
## Spécification V2 — intègre les 4 ajustements demandés par DILANE

**Statut : MILESTONE #3 CLÔTURÉ.** V2 implémentée, testée en boîte noire par Claude Code (9 critères, transactions Sepolia réelles), validée par DILANE avec une limite connue explicitement acceptée (voir "Résultats des tests" ci-dessous), code livré, commité et poussé sur GitHub.

**Statut V2 (historique) :** DILANE a validé l'architecture générale de la V1 sans réserve ("le flux est cohérent... c'est exactement le rôle que nous voulons donner à la blockchain") et tranché les 4 points d'arbitrage, avec une correction importante détectée en cours de relecture : la distinction `owner` / `certifier`, qui n'était pas dans la V1. Cette V2 intègre les 4 ajustements ciblés demandés, sans toucher au reste de l'architecture.

**Historique :** V1 proposée par Claude (architecture + 4 points d'arbitrage volontairement laissés ouverts) → DILANE valide l'architecture, tranche les 4 points, et identifie un problème que ni la V1 ni les points d'arbitrage n'avaient couvert (le wallet plateforme comme `msg.sender` unique aurait fait de la plateforme le propriétaire on-chain de tous les datasets, contredisant l'objectif de provenance) → cette V2 corrige ce point avec un modèle `owner`/`certifier` distinct.

---

## Objectif

Ancrer la preuve de provenance et d'intégrité d'un dataset sur la blockchain : calculer son empreinte, l'héberger sur IPFS, enregistrer un certificat on-chain (Sepolia), et permettre de vérifier a posteriori qu'un fichier récupéré correspond bien à sa version certifiée.

Ce Milestone ne modifie ni `qualite_donnees/` (Milestone #1) ni `insights_ia/` (Milestone #2) — il les consomme (score qualité pour `qualityScore`) sans les toucher.

## Architecture

```
backend/
├── qualite_donnees/     # Milestone #1 — INCHANGÉ
├── insights_ia/         # Milestone #2 — INCHANGÉ
├── confiance/
│   ├── __init__.py
│   ├── hachage.py         # empreinte SHA-256 du fichier dataset + hash des métadonnées
│   ├── stockage_ipfs.py   # upload/pinning vers Pinata, récupération d'un fichier via son CID
│   ├── client_blockchain.py  # web3.py : appel au smart contract (certifier, lire, vérifier)
│   └── certification.py   # orchestrateur : assemble hash + IPFS + appel contrat → certificat
contracts/
└── DatasetCertification.sol  # smart contract Solidity — conventions Solidity/Web3 en anglais (ADR-9),
                                # documentation et commentaires en français comme le reste du projet
```

**Flux de certification :**
```
CSV (chemin_fichier)
        │
        ├──→ hachage.py : SHA-256 du contenu brut du fichier → datasetHash
        │
        ├──→ stockage_ipfs.py : upload vers Pinata → ipfsCID
        │
        ├──→ qualite_donnees.generer_rapport() (déjà calculé, Milestone 1) → qualityScore
        │
        ├──→ hachage.py : SHA-256 d'un objet métadonnées structuré (voir ADR-2) → metadataHash
        │
        └──→ client_blockchain.py : appel certifyDataset(ownerAddress, datasetHash, ipfsCID,
             metadataHash, version, qualityScore) sur le smart contract (Sepolia) —
             ownerAddress = adresse déclarée par l'utilisateur (voir ADR-10), transmise par
             notre backend, pas nécessairement celle du wallet qui signe la transaction
                        │
                        ▼
        Certificat on-chain : owner = ownerAddress, certifier = msg.sender (wallet plateforme),
        timestamp ajouté par le contrat lui-même, datasetId auto-incrémenté et retourné (ADR-7)
```

**Flux de vérification :**
```
Fichier récupéré (ex. depuis IPFS via son CID)
        │
        ├──→ hachage.py : recalcule le SHA-256 du fichier récupéré
        │
        └──→ client_blockchain.py : lit le certificat on-chain pour ce datasetId,
             compare le hash recalculé à datasetHash on-chain
                        │
                        ▼
             Résultat : IDENTIQUE (intégrité confirmée) ou ALTÉRÉ (différence détectée)
```

## Le smart contract (`DatasetCertification.sol`)

Conventions Solidity/Web3 en anglais (ADR-9) — commentaires en français.

```solidity
struct DatasetCertificate {
    address owner;          // propriétaire DÉCLARÉ du dataset (fourni par l'utilisateur, pas forcément msg.sender)
    address certifier;      // wallet ayant réellement soumis la transaction (msg.sender) — voir ADR-10
    bytes32 datasetHash;
    string  ipfsCID;
    bytes32 metadataHash;
    uint16  version;
    uint16  qualityScore;   // score × 100 (ex. 9961 = 99.61) — voir ADR-3
    uint256 timestamp;      // block.timestamp, fixé par le contrat, jamais transmis par l'appelant
}

// datasetId : uint256 auto-incrémenté par le contrat (ADR-7) — le hash reste la preuve d'identité du contenu,
// le datasetId n'est qu'un index pratique

// certifyDataset(ownerAddress, datasetHash, ipfsCID, metadataHash, version, qualityScore)
//     → enregistre un nouveau certificat, owner = ownerAddress, certifier = msg.sender,
//       timestamp = block.timestamp ; retourne le datasetId attribué
// getCertificate(datasetId) → retourne le DatasetCertificate (lecture publique, gratuite)
// verifyHash(datasetId, recomputedHash) → bool (compare on-chain, sans transaction payante)
```

## Décisions (ADR)

| # | Décision | Justification |
|---|---|---|
| ADR-1 | `datasetHash` = SHA-256 du contenu brut du fichier (octets), calculé côté Python via `hashlib`, converti en `bytes32` pour le contrat | Indépendant du format/paramètres de chunking IPFS ; vérifiable par n'importe qui avec un simple `sha256sum`, sans dépendre de web3 |
| ADR-2 | `metadataHash` = SHA-256 d'un objet JSON structuré `{nom_fichier, score_global, scores_dimensions, date_certification}` (pas le rapport complet — trop volumineux et non stable pour un hash utile) | Permet de détecter si les métadonnées déclarées (notamment le score annoncé) ont été falsifiées séparément du contenu lui-même |
| ADR-3 | `qualityScore` stocké en `uint16`, valeur = score réel × 100 (ex. 99.61 → 9961) | Solidity n'a pas de type flottant ; ×100 préserve 2 décimales avec une plage largement suffisante (0-10000) |
| ADR-4 | `timestamp` est fixé par le contrat (`block.timestamp`), jamais transmis par l'appelant | Empêche un appelant de falsifier la date de certification |
| ADR-5 | Clé privée du wallet de certification lue depuis une variable d'environnement (`WALLET_PRIVATE_KEY`), jamais codée en dur ni journalisée ; `.env` déjà dans `.gitignore` | Même principe que `GROQ_API_KEY` (Milestone #2, ADR-4) — mais ici la conséquence d'une fuite est plus grave (perte de fonds/contrôle du wallet), donc à traiter avec le même sérieux minimum |
| ADR-6 | Si l'upload IPFS ou l'appel blockchain échoue, `certification.py` ne certifie rien de partiel : soit le certificat complet est enregistré, soit une erreur explicite est retournée — jamais un certificat avec un `ipfsCID` vide ou un hash incohérent | Un certificat partiel serait pire qu'une absence de certificat pour un projet de "Data Trust" |
| ADR-7 | `datasetId` est un identifiant numérique auto-incrémenté attribué par le smart contract. L'identité cryptographique du contenu reste assurée par `datasetHash` | Simple, standard, évite toute logique de dérivation côté contrat ; le hash — pas l'identifiant — est ce qui prouve le contenu |
| ADR-8 | Vérification manuelle du contrat déployé via l'interface Etherscan (upload du code source), pas de plugin `hardhat-verify` | Pas de dépendance ni de compte API supplémentaire pour le MVP |
| ADR-9 | Le code Solidity (`DatasetCertification.sol`) suit les conventions Web3/Solidity en anglais (noms de struct, de champs, de fonctions) ; les commentaires du contrat et toute la documentation du projet restent en français, comme le reste du code Python | Aligné sur les usages quasi universels de l'écosystème Solidity (OpenZeppelin, tutoriels, outillage), tout en gardant la lisibilité en français pour la documentation et la revue de code — décision de DILANE, qui corrige la proposition initiale de Claude (tout en français) |
| ADR-10 | Le certificat distingue `owner` (adresse déclarée comme propriétaire du dataset, fournie en paramètre à `certifyDataset` par notre backend — pas nécessairement le wallet qui signe la transaction) de `certifier` (`msg.sender`, le wallet plateforme qui soumet réellement la transaction). Pour le MVP, un wallet plateforme unique sert de `certifier` pour tous les datasets | Problème identifié par DILANE en relecture de la V1 : avec un seul wallet plateforme comme unique `msg.sender`, sans cette distinction, la plateforme deviendrait on-chain le "propriétaire" de tous les datasets certifiés — ce qui contredit l'objectif de provenance du projet. La connexion wallet utilisateur (qui permettrait à `owner` de devenir le signataire lui-même) reste prévue en Phase 4 |
| ADR-11 | `metadataHash` est calculé sur une sérialisation JSON canonique et déterministe de l'objet `{nom_fichier, score_global, scores_dimensions, date_certification}` (ADR-2) : clés triées par ordre alphabétique, encodage UTF-8, précision numérique fixe, dates au format ISO 8601 UTC, aucun espace superflu — équivalent en Python à `json.dumps(objet, sort_keys=True, separators=(",", ":"), ensure_ascii=True)` | Deux appels avec les mêmes métadonnées mais un ordre de clés ou un format différent produiraient sinon un hash différent, rendant la vérification a posteriori impossible à reproduire de façon fiable |

**Sur `datasetHash` et `ipfsCID` — deux questions distinctes.** `datasetHash` répond à « quel était exactement le contenu du fichier au moment de la certification ? » (une empreinte, vérifiable par quiconque avec un `sha256sum`, indépendante de tout service tiers). `ipfsCID` répond à « où peut-on récupérer ce fichier ? » (une adresse de récupération, dépendante du réseau IPFS et du pinning). Le certificat on-chain porte les deux car ils ne sont pas interchangeables : un CID valide ne garantit pas que le contenu récupéré est le bon (d'où la vérification du flux de vérification, qui recalcule et compare le hash) ; un hash correct sans CID ne permettrait pas de retrouver le fichier.

## Points d'arbitrage

Les 4 points laissés ouverts dans la V1 ont été tranchés par DILANE (relayés en parallèle à ChatGPT pour arbitrage) :

1. **Format de `datasetId`** → `uint256` auto-incrémenté côté contrat (ADR-7).
2. **Vérification Etherscan** → vérification manuelle via l'interface Etherscan pour le MVP (ADR-8).
3. **Langue du contrat Solidity** → conventions anglaises pour le code, documentation et commentaires en français (ADR-9) — DILANE a explicitement corrigé la proposition initiale de Claude (tout en français).
4. **Gestion du wallet de certification** → un wallet plateforme unique pour le MVP (connexion wallet utilisateur prévue en Phase 4), combiné au modèle `owner`/`certifier` (ADR-10) qui évite que ce choix ne fasse de la plateforme le propriétaire apparent de tous les datasets.

## Contraintes

- Respecte le cadrage MVP figé (CSV uniquement, réseau Sepolia uniquement)
- `qualite_donnees/` et `insights_ia/` ne sont pas modifiés
- La clé privée du wallet ne doit apparaître dans aucun fichier commité
- Aucune donnée brute du dataset n'est stockée on-chain — uniquement des empreintes et un CID (déjà acté dans le blueprint)
- Le module doit fonctionner sur les 5 datasets de démonstration (le dataset énergie, ~133 Mo, pose la question du coût/temps d'upload IPFS — à mesurer, pas supposer, comme pour le Milestone #2)

## Critères d'acceptation (pour Claude Code)

1. `hachage.py` calcule un SHA-256 identique à un calcul de référence indépendant (`hashlib.sha256` sur le même fichier, hors du module) sur les 5 datasets
2. `stockage_ipfs.py` upload un fichier vers IPFS et retourne un CID valide ; télécharger le fichier via ce CID puis recalculer son hash donne le même `datasetHash`
3. Le smart contract se déploie sans erreur sur Sepolia et est vérifiable manuellement sur Etherscan (ADR-8)
4. `certifyDataset()` enregistre un certificat lisible ensuite via `getCertificate()`, avec tous les champs corrects : `owner` = l'adresse déclarée transmise en paramètre (pas nécessairement l'appelant), `certifier` = `msg.sender` (le wallet plateforme), `timestamp` = horodatage du bloc (`block.timestamp`, jamais une valeur transmise par l'appelant) (ADR-10, ADR-4)
5. `verifyHash()` retourne `true` pour le hash correct et `false` pour un hash modifié (test avec un fichier délibérément altéré)
6. Aucune clé privée n'apparaît dans les logs, le JSON de sortie, ou tout fichier commité
7. Le pipeline complet (certification puis vérification) fonctionne de bout en bout sur au moins 3 des 5 datasets
8. `metadataHash` est reproductible : recalculer le hash à partir des mêmes métadonnées (même objet Python, appels séparés) donne exactement le même résultat, conformément à la sérialisation canonique définie en ADR-11
9. Mesure réelle de performance (jamais supposée, comme au Milestone #2) sur chacun des 5 datasets, avec un tableau détaillé : Dataset, Taille, Temps hash, Temps upload IPFS, CID obtenu, Temps transaction (certification on-chain), Gas utilisé, Coût estimé (en ETH et en équivalent fiat au taux du jour du test), Temps total de bout en bout — une attention particulière est portée au dataset énergie (~133 Mo), dont le coût/temps d'upload IPFS n'est pas à supposer

## Résultats des tests (Claude Code, boîte noire)

Batterie complète exécutée contre les 9 critères d'acceptation, avec de vraies transactions sur Sepolia (contrat déployé à `0xb475ddb4b4ef1ff3868b6f3384d784669abfb0ab`, vérifié sur Etherscan).

| # | Critère | Résultat |
|---|---|---|
| 1 | Hash SHA-256 identique à `hashlib` indépendant (5 datasets) | ✅ PASS |
| 2 | Upload/download IPFS + hash identique | ✅ PASS |
| 3 | Contrat déployé + vérifié sur Etherscan Sepolia | ✅ PASS |
| 4 | `certifyDataset`/`getCertificate` : `owner`/`certifier`/`timestamp` corrects (ADR-10) | ✅ PASS |
| 5 | `verifyHash` : `true` sur hash correct, `false` sur hash altéré | ✅ PASS |
| 6 | Aucune clé privée/JWT dans sortie, logs, ou fichiers commités | ✅ PASS |
| 7 | Pipeline bout-en-bout sur ≥3/5 datasets | ✅ PASS (4/5 réussis) |
| 8 | `metadataHash` reproductible, indépendant de l'ordre des clés (ADR-11) | ✅ PASS |
| 9 | Mesures de performance réelles sur les 5 datasets | 🟡 PARTIEL — voir ci-dessous |

**Sur le critère #9 — précision plutôt qu'arrondi optimiste (même rigueur qu'au Milestone #2) :** mesures complètes et réelles obtenues sur 4/5 datasets. Le 5ᵉ (dataset énergie, ~127 Mo) échoue de façon reproductible à l'upload IPFS (`ConnectionError`, testé à 3 reprises — 2× avec un timeout de 120s, échec à ~140s, puis 1× avec un timeout remonté à 600s, échec à ~623s). Le fait que le délai d'échec suive à peu près le timeout réglé, sans jamais aboutir, indique que ce n'est probablement pas qu'une question de patience — mais la cause exacte (limite réseau, comportement de l'upload monolithique face à un gros fichier, ou une limite Pinata non documentée clairement en HTTP) n'a pas été isolée avec certitude.

**Décision DILANE :** accepter cette limite telle quelle plutôt que d'investiguer davantage (ex. migration vers l'upload repris/par blocs TUS que Pinata recommande au-delà de 100 Mo) — le dataset énergie original (`household_power_consumption.txt`, ~127 Mo) reste tel quel dans le dépôt, sans échantillonnage ni remplacement. Cette limite (certification fiable jusqu'à ~30-50 Mo en l'état, pas encore validée au-delà) est à documenter explicitement dans le rapport technique final (section limites et perspectives) plutôt que passée sous silence — c'est un résultat mesuré, pas une supposition, ce qui est exactement l'esprit du projet.

**Trouvaille annexe pendant la clôture :** un bug de longue date dans `.gitignore` (une ligne contenant un espace entre chaque caractère, cassant le motif d'exclusion du dataset énergie depuis le Milestone #1) a été identifié et corrigé, avec l'ajout des exclusions Python (`__pycache__/`, `*.pyc`) qui manquaient totalement du fichier généré initialement pour un projet Node.js.

## Responsable exécution

- Spécification V1 : Claude (architecture + 4 points d'arbitrage volontairement laissés ouverts)
- V1 relayée par DILANE à ChatGPT pour arbitrage, puis validée par DILANE avec une correction identifiée en relecture (distinction `owner`/`certifier`, absente de la V1 et non couverte par les 4 points d'arbitrage)
- Spécification V2 : Claude — intègre les 4 ajustements demandés par DILANE
- Implémentation (`backend/confiance/` + `contracts/DatasetCertification.sol`) : Claude, avec tests locaux (chaîne EVM en mémoire) avant livraison
- Déploiement et vérification Etherscan sur Sepolia : DILANE (guidé par Claude)
- Tests contre les 9 critères d'acceptation : Claude Code (boîte noire, transactions Sepolia réelles)
- Validation finale et arbitrage sur la limite du critère #9 : DILANE — accepté en l'état, à documenter dans le rapport final
- Code livré, commité et poussé sur GitHub

**MILESTONE #3 CLÔTURÉ.**
