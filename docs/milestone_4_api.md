# Milestone #4 (partie 1) — Phase 4a : API Backend (FastAPI)

**Statut : V3 — spécification figée, GO ferme de DILANE pour l'implémentation.** Toutes les décisions architecturales sont tranchées : les 3 points d'arbitrage V1, l'idempotence en 3 cas, la récupération après crash, et l'Option B (modification additive de `insights_ia`) avec sa vérification de cohérence dataset.

**Historique :** V1 proposée par Claude (architecture ChatGPT + 3 ajouts techniques, 3 points d'arbitrage laissés ouverts) → DILANE relaie à ChatGPT, tranche les 3 points, affine l'idempotence en 3 cas (succès/en cours/échec), et ajoute la question de la récupération après crash → V2 intègre ces 6 ajustements, mais en creusant le point #1 (`/insights/rapports`), Claude trouve une contrainte technique non anticipée (le module recalcule toujours son rapport qualité en interne) et pose un nouveau point d'arbitrage (Option A vs B) → DILANE tranche pour l'Option B, ajoute une exigence de vérification de cohérence dataset (empêcher qu'un rapport qualité d'un fichier soit réutilisé avec les insights d'un autre) et deux critères de non-régression → cette V3 intègre ces 3 derniers ajustements et clôt la spécification.

---

## Objectif

Exposer les trois modules backend déjà validés (`qualite_donnees`, `insights_ia`, `confiance`) via une API HTTP, pour que le futur frontend Next.js (reste de la Phase 4) puisse les consommer. Cette couche n'introduit aucune nouvelle logique métier : FastAPI orchestre des jobs et appelle les fonctions déjà testées.

Ce Milestone ne modifie ni `qualite_donnees/`, ni `confiance/` au sens d'altérer une fonction existante (ADR-7, ADR-11 pour l'addition pure). Pour `insights_ia/`, une modification additive et rétrocompatible est apportée (ADR-12, Option B tranchée par DILANE) : un paramètre optionnel, comportement par défaut inchangé, avec une vérification de cohérence dataset et des tests de non-régression obligatoires.

## Architecture

```
backend/
├── qualite_donnees/     # INCHANGÉ
├── insights_ia/         # voir nouveau point d'arbitrage
├── confiance/            # INCHANGÉ (une fonction additive proposée, voir ADR-11)
└── api/
    ├── __init__.py
    ├── main.py               # instancie FastAPI, monte les routers, configure CORS, réconciliation au démarrage (ADR-10)
    ├── jobs/
    │   ├── __init__.py
    │   ├── gestionnaire.py    # JobManager : créer/lire/mettre à jour un job, persistance SQLite (ADR-3)
    │   ├── modeles.py         # schéma Job (id, type, statut, progression, etape, resultat, erreur, dates, champs internes)
    │   └── executants.py      # fonctions exécutées en arrière-plan, appellent les 3 modules (ADR-7)
    ├── routes/
    │   ├── qualite.py
    │   ├── insights.py
    │   ├── certifications.py
    │   └── jobs.py
    ├── schemas/                # modèles Pydantic requêtes/réponses
    └── uploads_temp/            # fichiers temporaires (gitignored), TTL configurable (ADR-9)
```

## Cycle de vie d'un job

Statuts : `en_attente` → `en_cours` → `termine` | `echec` | `echec_recuperable` (ADR-10)

```json
{
  "job_id": "uuid",
  "type": "rapport_qualite | rapport_intelligence | certification",
  "statut": "en_attente | en_cours | termine | echec | echec_recuperable",
  "progression": null,
  "etape": null,
  "resultat": null,
  "erreur": null,
  "cree_le": "2026-08-26T18:00:00Z",
  "mis_a_jour_le": "2026-08-26T18:00:00Z"
}
```

`progression` reste **`null` tant qu'un job est `en_cours`**, pour `rapport_qualite`, `rapport_intelligence` et `certification` (ADR-4 révisée) : aucun des trois modules n'expose de callback de progression réelle aujourd'hui, et une fausse progression (20 %, 40 %...) serait trompeuse. `etape` reste aussi `null` ou grossier (ex. `"certification"` sans détail par sous-étape) tant que les modules ne sont pas enrichis pour ça — pas de modification de `qualite_donnees/`, `insights_ia/` ou `confiance/` juste pour alimenter une barre de progression.

Champs internes au `JobManager`, **jamais exposés** dans les réponses `GET /jobs/{job_id}` (risque de fuite de chemins serveur) : `chemin_fichier_temp` (pour retrouver le fichier source d'un job qualité), `dataset_hash` (pour l'idempotence des certifications), `transaction_hash` (dès qu'elle est connue, avant même confirmation — voir ADR-10).

## Endpoints

**Qualité**
- `POST /api/v1/qualite/rapports` — `multipart/form-data` (fichier CSV) → `202 Accepted {"job_id", "statut": "en_attente"}`

**Insights**
- `POST /api/v1/insights/rapports` — JSON `{"job_id": "uuid"}`, référence à un job `rapport_qualite` **terminé** (ADR-9-bis, tranché par DILANE — Option B, ADR-12). Retourne `404 job_introuvable` si le job n'existe pas, `409 job_qualite_non_termine` s'il existe mais n'est pas `termine`, `400 type_job_incorrect` s'il n'est pas de type `rapport_qualite`, ou `409 dataset_incoherent` si le fichier retrouvé ne correspond plus au hash enregistré au moment du job qualité (ADR-12) → `202 Accepted {"job_id", "statut": "en_attente"}`

**Certification**
- `POST /api/v1/certifications` — `multipart/form-data` (fichier, `owner_address`, `version` optionnel défaut=1). Vérifie d'abord l'idempotence (ADR-5, précisée) :
  - un certificat **terminé** existe déjà pour ce hash → `200` avec ce résultat directement, aucun nouveau job
  - un job **en cours** (`en_attente`/`en_cours`) existe déjà pour ce hash → `200 {"job_id": "...", "statut": "en_cours"}`, le job existant, aucune nouvelle transaction
  - le seul job précédent pour ce hash s'est **terminé en échec** → nouvelle tentative autorisée, nouveau `job_id`
  - sinon (premier essai) → `202 Accepted {"job_id", "statut": "en_attente"}`
- `GET /api/v1/certifications/{dataset_id}` — lecture synchrone on-chain (via `confiance.obtenir_certificat`) → `200` le certificat, ou `404`
- `POST /api/v1/certifications/{dataset_id}/verifier` — `multipart/form-data` (fichier), synchrone (ADR-4) → `200 {"identique", "dataset_id", "hash_recalcule", "hash_certifie"}`

**Jobs**
- `GET /api/v1/jobs/{job_id}` — `200` le job complet (champs internes exclus), ou `404`

**Santé**
- `GET /api/v1/health` — `200 {"statut": "ok"}`

## Gestion des erreurs

Format uniforme pour toute réponse 4xx/5xx :
```json
{"erreur": {"code": "...", "message": "..."}}
```
Codes prévus (liste extensible) : `fichier_absent`, `fichier_invalide`, `job_introuvable`, `job_qualite_non_termine`, `type_job_incorrect`, `dataset_incoherent`, `dataset_introuvable`, `upload_ipfs_echec`, `transaction_blockchain_echec` (ces deux derniers repris tels quels du champ `"erreur"` déjà retourné par `confiance.py` — jamais de certificat partiel, ADR-6 du Milestone #3 reste valable ici).

## Décisions (ADR)

| # | Décision | Justification |
|---|---|---|
| ADR-1 | Modèle asynchrone par jobs + polling HTTP pour qualité/insights/certification ; pas de WebSocket, pas de Celery/Redis pour le MVP | Proposition ChatGPT — évite les timeouts HTTP sur des opérations de plusieurs secondes à plusieurs minutes (IPFS, transaction Sepolia), sans ajouter d'infrastructure distribuée prématurée |
| ADR-2 | `JobManager` découplé de l'`ExecutionBackend` (aujourd'hui : `BackgroundTasks` FastAPI en process local ; remplaçable plus tard par Celery/Redis sans changer les endpoints) | Permet de faire évoluer le moteur d'exécution sans casser le contrat API — proposition ChatGPT |
| ADR-3 | Persistance des jobs en SQLite (fichier local unique), pas en mémoire | Un job en cours (notamment une certification avec transaction blockchain déjà envoyée) ne doit pas perdre son suivi si le serveur FastAPI redémarre — ajout de Claude, validé par DILANE |
| ADR-4 | `POST /certifications/{dataset_id}/verifier` reste synchrone ; `progression`/`etape` restent `null`/grossiers pour tous les jobs tant que les modules métier n'exposent pas de callback réel | Le hash est quasi instantané (Milestone #3 : <1ms mesuré). Sur la progression : DILANE tranche explicitement pour "une progression inconnue vaut mieux qu'une progression fictive" plutôt que des pourcentages non mesurés — pas de modification de `confiance.py`, `qualite_donnees/` ou `insights_ia/` juste pour ça |
| ADR-5 | Idempotence de la certification gérée **côté API** (registre local `datasetHash` → job), **avec 3 cas distincts** : (a) certification terminée → retourne le résultat existant ; (b) job en cours (même hash) → retourne le job existant, aucune nouvelle transaction ; (c) dernier job en échec → nouvelle tentative autorisée, nouveau job | Le contrat déployé (déjà vérifié sur Etherscan) n'a pas de fonction de recherche par hash — un registre applicatif évite de casser ce qui est déjà en production. La distinction des 3 cas est l'arbitrage de DILANE (relayé de ChatGPT) : un échec réseau/IPFS ne veut pas dire que le dataset est certifié, il doit rester "retentable" |
| ADR-6 | Le fichier uploadé est sauvegardé sur disque de façon **synchrone** dans le handler `POST`, avant que le `job_id` soit renvoyé | `UploadFile` de FastAPI est un flux lié à la requête HTTP, indisponible pour une tâche en arrière-plan après l'envoi de la réponse — ajout de Claude |
| ADR-7 | FastAPI n'implémente aucune logique métier — chaque route/job appelle uniquement les fonctions publiques déjà exposées, jamais une réimplémentation | Respecte le fait que les trois modules sont déjà testés et validés (Milestones #1-3) ; FastAPI reste une couche d'exposition, pas une couche métier — proposition ChatGPT, confirmée par DILANE ("l'API ne doit pas modifier les modules métier") |
| ADR-8 | Chaque module garde son propre type de job/endpoint (pas d'endpoint unique "pipeline complet") | Permet de tester chaque module isolément et de le réutiliser indépendamment — confirmé explicitement par DILANE ("je ne veux pas d'un `POST /pipeline`, trop couplé") |
| ADR-9 | Fichiers temporaires nommés par un UUID généré par l'application (jamais le nom fourni par l'utilisateur utilisé dans un chemin disque) ; durée de rétention `UPLOAD_TTL_HOURS` configurable (variable d'environnement, pas une constante codée en dur) ; un job `en_attente`/`en_cours` n'est **jamais** nettoyé même si son fichier dépasse le TTL — seuls les fichiers de jobs `termine`/`echec`/`echec_recuperable` sont éligibles au nettoyage | Sécurité (éviter une traversée de chemin via un nom de fichier utilisateur non filtré) + fiabilité (un nettoyage automatique ne doit jamais supprimer un fichier qu'un job actif utilise encore) — arbitrage de DILANE |
| ADR-9-bis | `/insights/rapports` reçoit exclusivement `{"job_id": "uuid"}` référençant un job `rapport_qualite` déjà `termine` — pas d'upload direct en alternative | Reflète le pipeline verrouillé Phase 1 → Phase 2 ; sépare clairement "`/qualite` produit, `/insights` consomme" — arbitrage explicite de DILANE, qui écarte l'option "upload OU job_id" proposée en V1 |
| ADR-10 | Au démarrage de FastAPI, tout job trouvé `en_cours` en base est marqué `echec_recuperable` plutôt que laissé tel quel indéfiniment. Pour un job de certification qui a déjà un `transaction_hash` enregistré (la transaction a pu être envoyée avant le crash), une fonction additive `confiance.client_blockchain.obtenir_recu_transaction(hash)` (nouvelle fonction, n'altère aucune fonction existante) est appelée pour vérifier si elle a été confirmée entre-temps ; si oui, le job est réconcilié vers `termine` avec le résultat réel plutôt que perdu. **Précision de DILANE : `echec_recuperable` signifie "plus suivi activement par le processus actuel, nouvelle tentative autorisée" — pas "la certification a échoué" ; une transaction introuvable au redémarrage peut théoriquement se confirmer plus tard** | DILANE : "la blockchain peut avoir reçu la transaction alors que notre job SQLite reste en_cours" — un crash pendant `BackgroundTasks` (process local, pas de file de tâches durable) ne doit pas laisser un job orphelin sans qu'on sache s'il a réellement abouti on-chain |
| ADR-11 | `client_blockchain.py` gagne une fonction additive `obtenir_recu_transaction(hash_transaction)` (lecture seule, ne modifie aucune fonction existante ni leur signature) | Nécessaire pour ADR-10 — reste conforme à la règle "ne pas modifier `confiance/`" au sens strict : aucune fonction existante n'est touchée, uniquement une nouvelle ajoutée |
| ADR-12 | **Option B retenue** (DILANE) : `insights_ia.generer_rapport_intelligence(chemin_fichier, modele_llm=None, rapport_qualite=None)` gagne un paramètre optionnel. `rapport_qualite=None` → comportement actuel inchangé à l'identique (aucune régression pour un appel existant). `rapport_qualite` fourni → la fonction saute son appel interne à `generer_rapport()` et réutilise celui donné (`construire_artefact()` continue de relire le fichier séparément — nécessaire pour la matrice de features des anomalies, ADR-12 n'élimine pas cette seconde lecture). **Vérification de cohérence obligatoire** : le job qualité conserve en interne un `dataset_hash` (SHA-256 du fichier, via `confiance.hachage.calculer_hash_fichier()` — réutilisation en lecture seule d'une fonction déjà validée, pas une duplication de logique) calculé à la création du job ; avant d'appeler `generer_rapport_intelligence()` avec ce rapport, l'API recalcule le hash du fichier à `chemin_fichier_temp` et le compare — mismatch → `409 dataset_incoherent`, rien n'est exécuté | DILANE : "on touche un module déjà validé, additif et rétrocompatible mais pas *sans risque* — sous réserve de tests de non-régression" (critère #16) ; et le risque identifié par DILANE d'un rapport qualité du dataset A appliqué au fichier du dataset B ("insights de B + score qualité de A", incompatible avec l'esprit Data Trust) impose une vérification explicite plutôt qu'une confiance implicite dans la cohérence `job_id` ↔ fichier |

## Contraintes

- Ne modifie ni `qualite_donnees/`, ni `confiance/` (au sens d'altérer une fonction existante — une addition pure est admise, ADR-11) — nouvelle couche principalement dans `backend/api/`
- Aucune clé (`GROQ_API_KEY`, `PINATA_JWT`, `WALLET_PRIVATE_KEY`) ne doit apparaître dans une réponse HTTP, un log, ou un message d'erreur
- CORS activé pour permettre au futur frontend Next.js (origine différente en développement) d'appeler l'API
- Aucun chemin de fichier serveur ne doit apparaître dans une réponse HTTP exposée au client

## Modification de `insights_ia/` — Option B tranchée (ADR-12)

Décision de DILANE, close : `insights_ia.generer_rapport_intelligence()` gagne un paramètre optionnel `rapport_qualite=None`, rétrocompatible à 100 % (comportement identique pour tout appel existant sans ce paramètre). Quand il est fourni, la fonction saute son appel interne à `generer_rapport()` et réutilise le rapport donné, avec une vérification de cohérence dataset obligatoire côté API avant l'appel (ADR-12). `construire_artefact()` continue de relire le fichier séparément (nécessaire à la matrice de features des anomalies, indépendamment du rapport qualité) — l'Option B élimine le recalcul du rapport qualité, pas cette seconde lecture.

DILANE a explicitement nuancé la présentation initiale de cette modification comme "sans risque" : c'est une modification **additive, rétrocompatible et à faible risque, sous réserve de tests de non-régression** — d'où les critères #16 et #17 ci-dessous, qui conditionnent la clôture de ce Milestone au même titre que les autres.

## Récupération après crash / redémarrage

Documenté explicitement comme demandé par DILANE (ADR-10) :

1. Au démarrage de FastAPI, le `JobManager` parcourt tous les jobs `en_cours` en base SQLite.
2. Pour un job de certification avec un `transaction_hash` déjà enregistré : appel à `obtenir_recu_transaction(hash)` (ADR-11) pour vérifier son statut réel sur Sepolia.
   - Transaction confirmée avec succès → le job est réconcilié en `termine`, avec le `dataset_id` et le résultat complet relus via `confiance.obtenir_certificat()`.
   - Transaction introuvable/en attente sur le réseau → le job passe à `echec_recuperable` (pas `echec` : il pourrait encore se confirmer plus tard, mais on ne le suit plus activement).
3. Pour tout autre job `en_cours` sans `transaction_hash` (crash avant l'étape blockchain, ou job qualité/insights) : passage direct à `echec_recuperable`.
4. Un job `echec_recuperable` compte comme un `echec` pour l'idempotence (ADR-5, cas c) — une nouvelle tentative est autorisée.
5. **Limite assumée pour ce Milestone** : la réconciliation ne se déclenche qu'au démarrage du serveur, pas en continu pendant qu'il tourne — un crash suivi d'un redémarrage rapide est couvert, un job qui reste bloqué sans que le serveur ne redémarre ne l'est pas. Un mécanisme de nettoyage périodique (ex. tâche planifiée) est une amélioration future, pas dans le périmètre de ce Milestone.

## Critères d'acceptation (pour Claude Code)

1. `POST /qualite/rapports` retourne `202` + `job_id` ; `GET /jobs/{job_id}` passe de `en_attente` à `termine` avec un `resultat` identique à un appel direct de `qualite_donnees.generer_rapport()` sur le même fichier
2. `POST /insights/rapports` avec un `job_id` de qualité `termine` valide retourne `202` + `job_id` ; le job se termine avec un résultat cohérent avec un appel direct à `insights_ia.generer_rapport_intelligence()`
3. `POST /insights/rapports` avec un `job_id` inexistant, non `termine`, ou d'un autre type retourne l'erreur appropriée (`404`/`409`/`400`) sans créer de job
4. `POST /certifications` avec un fichier jamais certifié retourne `202` + `job_id` ; le job se termine avec un `resultat` contenant `dataset_id`, `hash_transaction`, etc. — vérifiable sur Etherscan
5. Rejouer `POST /certifications` avec exactement le même fichier une fois le premier certificat `termine` retourne le résultat existant (`200`, pas un nouveau `job_id`) — idempotence cas (a)
6. Rejouer `POST /certifications` avec le même fichier **pendant qu'un job est encore `en_cours`** pour ce hash retourne le job existant (`200`, même `job_id`), sans déclencher de deuxième transaction — idempotence cas (b)
7. Après un job de certification terminé en `echec` (ex. upload IPFS simulé en échec), rejouer `POST /certifications` avec le même fichier crée un **nouveau** `job_id` — idempotence cas (c)
8. `GET /certifications/{dataset_id}` sur un certificat existant retourne les mêmes champs qu'un appel direct à `confiance.obtenir_certificat()`
9. `POST /certifications/{dataset_id}/verifier` est synchrone (pas de `job_id` renvoyé), répond `identique`/`altéré` correctement
10. Un `job_id` inexistant sur `GET /jobs/{job_id}` retourne `404` avec le format d'erreur uniforme
11. Aucune clé (`GROQ_API_KEY`, `PINATA_JWT`, `WALLET_PRIVATE_KEY`) ni chemin de fichier serveur n'apparaît dans une réponse HTTP ni dans les logs du serveur
12. Après redémarrage du serveur FastAPI, un job déjà terminé reste consultable via `GET /jobs/{job_id}` (persistance SQLite, ADR-3)
13. Un job simulé `en_cours` au moment d'un redémarrage est retrouvé `echec_recuperable` après le redémarrage (réconciliation, ADR-10) — et si un `transaction_hash` valide lui était associé et confirmé entre-temps, il est retrouvé `termine` avec le bon résultat à la place
14. Un fichier temporaire lié à un job `en_attente`/`en_cours` n'est jamais supprimé par le nettoyage, même après expiration du `UPLOAD_TTL_HOURS`
15. CORS autorise une requête depuis une origine différente (ex. `localhost:3000`, le futur Next.js)
16. **Non-régression Phase 2** — `insights_ia.generer_rapport_intelligence(chemin_fichier)` appelé sans `rapport_qualite` (comme le fait déjà tout code existant) produit un résultat du même type/structure que celui validé au Milestone #2 — aucune régression introduite par l'ajout du paramètre optionnel (ADR-12)
17. **Cohérence dataset** — passer délibérément un `job_id` de rapport qualité associé à un fichier A, alors que le fichier réellement à `chemin_fichier_temp` a été altéré/remplacé (simulé en test), doit être rejeté explicitement (`409 dataset_incoherent`), jamais accepté silencieusement avec un résultat mêlant les deux datasets (ADR-12)

## Responsable exécution

- Proposition d'architecture : ChatGPT (arbitrage demandé par DILANE)
- Spécification V1 : Claude — intègre la proposition ChatGPT + 3 ajouts techniques, 3 points d'arbitrage laissés ouverts
- Arbitrage V1 → V2 : DILANE (relayé à ChatGPT) — tranche les 3 points, précise l'idempotence en 3 cas, ajoute la récupération après crash
- Spécification V2 : Claude — intègre les 6 ajustements + un nouveau point d'arbitrage trouvé en creusant l'ADR-9-bis
- Arbitrage V2 → V3 : DILANE — tranche pour l'Option B, ajoute la vérification de cohérence dataset et deux critères de non-régression
- Spécification V3 (ce document) : Claude — intègre ces 3 derniers ajustements
- **GO ferme donné par DILANE** — spécification close, implémentation à démarrer
- Implémentation : Claude
- Tests contre les 17 critères ci-dessus : Claude Code (boîte noire)
- Validation finale : DILANE
