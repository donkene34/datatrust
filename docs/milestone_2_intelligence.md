# Milestone #2 — Phase 2 : Intelligence
## Spécification V2.1 — intègre les 4 derniers ajustements de ChatGPT (quasi-GO)

**Statut :** V2.1 — **VALIDÉ par DILANE**. ChatGPT avait validé l'architecture de la V2 (artefact analytique) sans réserve et demandé 4 petits ajustements ; cette V2.1 les intègre. Implémentation en cours.

**Historique :** V1 proposée par Claude → NO-GO conditionnel de ChatGPT/DILANE : incohérence entre "ne jamais relire le CSV" et "Isolation Forest a besoin de la matrice ligne par ligne" → V2 introduit un artefact analytique interne pour résoudre la contradiction sans toucher au contrat déjà validé du Milestone #1 → ChatGPT valide l'architecture de la V2 (plus de blocage) et demande 4 ajustements : (A) assouplir la règle "≥ 3 insights" pour la baser sur la pertinence réelle des données plutôt qu'un chiffre imposé, (B) rendre le champ `source` d'un insight structuré (objet machine-readable) plutôt que du texte libre, (C) fixer un `random_state` pour la reproductibilité d'Isolation Forest, (D) exiger une mesure réelle des performances sur le dataset énergie plutôt qu'une supposition → cette V2.1 intègre les 4 points.

**Principe clarifié (corrige une généralisation trop large de la V1) :** ce n'est pas "Milestone #2 ne relit jamais le CSV" — c'est **"le LLM ne reçoit jamais le CSV brut ni les observations individuelles"**. Les modules Data Science internes (détection d'anomalies, visualisations) ont, eux, légitimement besoin des données réelles — c'est ce que dit déjà le Blueprint §3 : les étapes 1 à 5 (profilage, qualité, distributions, anomalies, visualisations) opèrent sur les données ; seule l'étape 6 (transmission au LLM) est restreinte aux résultats structurés.

---

## Objectif

Construire l'AI Insights Engine : détecter des anomalies multivariées, générer des visualisations adaptées, et produire (via l'API Groq) un résumé, des insights et des recommandations en langage naturel — le LLM interprète des résultats déjà calculés, il ne voit jamais le CSV brut ni les visualisations elles-mêmes (notre LLM est un modèle texte, pas vision).

## Architecture

```
backend/
├── qualite_donnees/            # Milestone #1, déjà livré — INCHANGÉ
├── insights_ia/
│   ├── __init__.py
│   ├── artefact_analytique.py   # NOUVEAU (correction #1/#2) — construit la matrice de features
│   │                             # à partir du tableau, pour usage interne du pipeline uniquement
│   ├── anomalies.py             # détection multivariée (Isolation Forest), consomme l'artefact
│   ├── visualisations.py        # génère les graphiques (consomme l'artefact + le profil)
│   ├── invite.py                # construit le prompt structuré envoyé au LLM
│   ├── client_llm.py            # appel à l'API Groq, gestion des erreurs réseau/clé absente
│   └── moteur.py                # assemble tout : artefact + anomalies + visualisations + LLM → JSON final
└── tests/                       # Claude Code
```

**Flux (corrigé) :**
```
                            CSV (chemin_fichier)
                                    │
                 ┌──────────────────┴──────────────────┐
                 ↓                                      ↓
      qualite_donnees.generer_rapport()        artefact_analytique.construire()
      (Milestone 1, appelé tel quel,            (Milestone 2, charge le CSV via
       INCHANGÉ)                                 qualite_donnees.chargeur — même
                 │                                loader, même détection de séparateur)
                 ↓                                      ↓
         rapport qualité                    ArtefactAnalytique (matrice numérique,
         (score, dimensions,                 en mémoire, usage interne uniquement)
          profil, correlations)                         │
                 │                          ┌────────────┴────────────┐
                 │                          ↓                         ↓
                 │                   anomalies.py               visualisations.py
                 │                   (Isolation Forest)          (histogrammes, heatmap)
                 │                          │                         │
                 └──────────────┬───────────┴─────────────────────────┘
                                 ↓
                          invite.py (construit le prompt : UNIQUEMENT rapport +
                                     résultats d'anomalies + statistiques descriptives
                                     des visualisations — jamais l'artefact brut,
                                     jamais une image)
                                 ↓
                          client_llm.py (appel Groq)
                                 ↓
                          moteur.py → JSON final
```

**Point important :** `artefact_analytique.py` recharge le CSV via `qualite_donnees.chargeur.charger_csv()` (le même loader que le Milestone 1, donc même détection de séparateur/valeurs manquantes). C'est un second chargement du fichier (léger surcoût, acceptable pour le MVP) plutôt qu'une modification de l'API publique `generer_rapport()` du Milestone 1 — le contrat déjà validé du Milestone #1 reste intact (correction #2).

## L'artefact analytique (correction #1)

Objet interne, **jamais exposé au LLM, jamais sérialisé tel quel dans le JSON final** — sert uniquement de donnée d'entrée pour `anomalies.py` et `visualisations.py`.

```python
ArtefactAnalytique = {
    "identifiant_dataset": str,
    "nombre_observations": int,
    "colonnes_numeriques": [str, ...],       # colonnes retenues pour Isolation Forest
    "colonnes_exclues": [{"nom": str, "raison": str}, ...],  # ex. taux de manquants trop élevé
    "matrice_features": np.ndarray,          # observations × colonnes numériques, imputée
    "metadonnees_transformation": {
        "imputation": "mediane",             # ADR-6 : comment les NaN ont été traités
        "colonnes_imputees": [str, ...],
    },
}
```

**Règle de construction (ADR-6) :** seules les colonnes numériques avec un taux de valeurs manquantes ≤ 50 % sont retenues ; les valeurs manquantes restantes sont imputées par la médiane de la colonne (Isolation Forest ne gère pas nativement les `NaN`). Les colonnes exclues et la méthode d'imputation sont documentées dans `metadonnees_transformation`, pour que les insights générés puissent, si besoin, mentionner cette limite.

## Décisions (ADR)

| # | Décision | Justification |
|---|---|---|
| ADR-1 | Détection d'anomalies multivariée via Isolation Forest (scikit-learn) sur la `matrice_features` de l'artefact analytique, avec un `random_state` fixe (ex. `42`) codé en dur dans `anomalies.py` | Complète les outliers par colonne du Milestone 1 (IQR) par une détection qui capture des combinaisons anormales sur plusieurs colonnes ensemble — anticipé dans l'ADR-4 du Milestone 1. Le `random_state` fixe garantit un résultat identique à chaque exécution sur le même dataset — essentiel pour un projet de "Data Trust" dont les scores doivent être reproductibles et non aléatoires *(ajout correction #3, ChatGPT V2.1)* |
| ADR-2 | Visualisations générées avec Matplotlib à partir de l'artefact (histogrammes) et du profil (heatmap de corrélations), encodées en base64, intégrées au JSON final — **mais jamais transmises au LLM** | Le frontend (Phase 4) n'existe pas encore ; le base64 garde le JSON autoportant. Précision ajoutée : notre LLM (Groq) est un modèle texte, pas vision — les images ne pourraient de toute façon pas lui être envoyées. Décision provisoire signalée par ChatGPT : à revoir en Phase 4 (données de graphique brutes pour Plotly/Recharts plutôt que des images pré-rendues) |
| ADR-3 | Le prompt envoyé au LLM ne contient **ni le CSV brut, ni l'artefact analytique brut, ni les observations individuelles** — uniquement le rapport qualité (Milestone 1) + les résultats agrégés des anomalies (scores, colonnes impliquées) + les statistiques descriptives des visualisations (jamais les images) | Le LLM interprète des résultats déjà calculés ; principe du Blueprint §3, reformulé précisément après la correction de la V1 |
| ADR-4 | Clé API Groq lue depuis une variable d'environnement (`GROQ_API_KEY`), jamais codée en dur ni journalisée | Sécurité de base ; `.env` dans `.gitignore` |
| ADR-5 | Si l'appel LLM échoue (clé absente, erreur réseau, quota dépassé), le moteur ne plante pas : il retourne un JSON avec un champ d'erreur explicite, le reste du rapport (qualité, profil, anomalies, visualisations) reste disponible | Un problème réseau ponctuel ne doit pas rendre tout le rapport inutilisable |
| ADR-6 *(nouveau)* | L'artefact analytique exclut les colonnes numériques à plus de 50 % de valeurs manquantes, impute le reste par la médiane, et documente ce choix dans `metadonnees_transformation` | Isolation Forest ne gère pas les `NaN` nativement ; ce choix doit être traçable, pas silencieux |
| ADR-7 *(nouveau, correction #4)* | Le JSON produit par le LLM suit un contrat strict : `resume` (texte), `insights[]` (`titre`, `description`, `importance`, `source`), `recommandations[]` (`titre`, `description`) | Le frontend (Phase 4) doit pouvoir afficher ces éléments sans parser du texte libre |
| ADR-8 *(révisé, correction #2 V2.1)* | Chaque insight généré doit inclure un champ `source` **structuré** (objet JSON, pas du texte libre) citant précisément la donnée analytique dont il est tiré : `{"type": "statistique \| anomalie \| correlation", "element": "...", "metrique": "...", "valeur": 0}` — le contrat exact du champ `source` est imposé dans le prompt système envoyé au LLM | Traçabilité contre les hallucinations : un insight non rattachable à une donnée fournie ne doit pas apparaître. La structuration en objet (plutôt qu'une phrase libre) rend la vérification automatique (critère 6) fiable par recoupement de champs plutôt que par analyse de texte — plus robuste et directement exploitable par le frontend (Phase 4). Particulièrement important pour un projet de "Data Trust" *(V2 demandait du texte libre ; ChatGPT a demandé la structuration en V2.1)* |

## Sortie de `anomalies.py` et compression pour le LLM (ADR-9, ADR-10 — décision DILANE, post-V2.1)

Pendant l'implémentation, un point technique réel est apparu : avec `contamination="auto"` (réglage par défaut de scikit-learn), le taux d'anomalies détectées n'est pas calibré pour viser un pourcentage précis — il peut être élevé sans que cela signifie que les données sont mauvaises (ex. mesuré en implémentation : 36 % sur le dataset RH, 68 % sur le dataset médical, contre seulement 3,9 % sur le dataset immobilier). Question posée à DILANE : imposer un `contamination` numérique fixe (ex. `0.05`) pour éviter ces taux élevés, ou garder `"auto"` et gérer le problème en aval ? DILANE a tranché en faveur de la seconde option, avec une justification retenue telle quelle : imposer 5 % a priori serait arbitraire sans connaissance du domaine (un dataset médical n'a aucune raison objective d'avoir exactement 5 % d'anomalies) — la calibration doit se faire par une hiérarchisation *post-hoc* (résumé + cas extrêmes), pas par une hypothèse a priori sur le taux.

```
anomalies.py                                    invite.py
Isolation Forest (contamination="auto")    →     résumé statistique (nombre, taux, méthode,
    │                                              paramètres, score min/max)
    ▼                                             + N anomalies aux scores les plus extrêmes
Liste COMPLÈTE des anomalies                     (jamais les centaines de lignes brutes)
(indice, score, colonnes)                              │
                                                         ▼
                                                        LLM
```

| # | Décision | Justification |
|---|---|---|
| ADR-9 *(nouveau, décision DILANE)* | `anomalies.py` garde `contamination="auto"` (pas de taux imposé arbitrairement) et retourne la liste **complète** des anomalies, plus `methode` (`"isolation_forest"`), `parametres` (`{contamination, random_state}`) et `taux_anomalies` en tête de sa sortie | Un taux fixé a priori (ex. 5 %) serait arbitraire sans connaissance du domaine du dataset. `methode`/`parametres` accompagnent systématiquement le résultat pour que toute interprétation en aval (LLM ou humain) sache comment il a été obtenu |
| ADR-10 *(nouveau, décision DILANE)* | `invite.py` ne transmet jamais la liste complète des anomalies au LLM : uniquement un résumé (`nombre_observations`, `nombre_anomalies`, `taux_anomalies`, `score_min`, `score_max`, `methode`, `parametres`) + les **10 anomalies aux scores les plus extrêmes** (constante `NOMBRE_ANOMALIES_EXTREMES = 10`, ajustable). Le prompt système impose explicitement au LLM : une anomalie statistique (isolable selon le modèle) n'est pas la même chose qu'une anomalie métier (une erreur, une fraude, une donnée pathologique) — le LLM doit formuler ses insights en conséquence (ex. "mérite une investigation complémentaire", jamais une affirmation catégorique du type "36 % des employés ont des données incorrectes") | Envoyer des centaines de lignes brutes au LLM serait à la fois coûteux et peu exploitable ; surtout, un taux élevé sans ce garde-fou risquerait de produire des insights trompeurs, contraires à l'esprit "Data Trust" du projet |

*(Note de rigueur, demandée par DILANE : le critère d'acceptation 11 — reproductibilité d'Isolation Forest — a été vérifié sur 4 des 5 datasets de démonstration lors de l'implémentation ; le dataset énergie n'était pas encore disponible dans l'environnement de test à ce moment. Validation complète sur les 5/5 prévue à la tâche de mesure de performance, critère 12.)*

## Contrat de sortie du LLM (révisé, correction #2 V2.1 — `source` structuré)

```json
{
  "resume": "...",
  "insights": [
    {
      "titre": "...",
      "description": "...",
      "importance": "elevee | moyenne | faible",
      "source": {
        "type": "statistique | anomalie | correlation",
        "element": "nom de la colonne ou de la paire de colonnes concernée",
        "metrique": "ex. ecart_type, moyenne, taux_manquants, score_isolation_forest, coefficient",
        "valeur": 0
      }
    }
  ],
  "recommandations": [
    { "titre": "...", "description": "..." }
  ]
}
```

**Exemples concrets de `source` selon `type` :**
- statistique : `{"type": "statistique", "element": "revenu_annuel", "metrique": "ecart_type", "valeur": 310000}`
- anomalie : `{"type": "anomalie", "element": "isolation_forest", "metrique": "score", "valeur": -0.62}`
- corrélation : `{"type": "correlation", "element": "surface_m2 / prix", "metrique": "coefficient", "valeur": 0.87}`

Ce contrat remplace le champ `source` texte libre de la V2 : un objet structuré, avec un `type` fermé et une `valeur` numérique, permet une vérification automatique fiable (critère 6) au lieu d'une recherche de sous-chaîne dans une phrase.

## Contraintes

- Respecte le cadrage MVP figé (CSV uniquement)
- `qualite_donnees/` (Milestone 1) n'est pas modifié — son contrat JSON V3 reste tel que validé
- La clé API ne doit apparaître dans aucun fichier commité (`.env` dans `.gitignore`)
- L'artefact analytique n'est jamais sérialisé tel quel dans une sortie publique (ni JSON de sortie, ni prompt LLM)
- Le module doit fonctionner sur les 5 datasets de démonstration, y compris le dataset énergie (~2M lignes). Isolation Forest de scikit-learn sous-échantillonne par défaut, ce qui rend le temps de calcul probablement raisonnable — mais cette hypothèse doit être **vérifiée par une mesure réelle**, pas supposée (voir critère d'acceptation 12)

## Critères d'acceptation (pour Claude Code)

1. `artefact_analytique.construire()` s'exécute sans erreur sur les 5 datasets ; `matrice_features` ne contient aucun `NaN` ; les colonnes exclues (>50 % manquant) sont bien listées dans `colonnes_exclues`
2. `anomalies.py` s'exécute sans erreur sur les 5 datasets et retourne une liste d'anomalies multivariées (potentiellement vide), chaque anomalie référençant un score et les colonnes numériques utilisées
3. `visualisations.py` génère au moins 2 graphiques par dataset (histogramme d'une variable numérique clé, heatmap de corrélations), encodés en base64 valides (décodables en image)
4. *(précisé, ADR-10)* Le prompt construit par `invite.py` ne contient : ni valeur de cellule individuelle du CSV, ni la `matrice_features` de l'artefact, ni de chaîne base64 d'image, ni la liste complète des anomalies détectées — uniquement des agrégats (rapport Milestone 1 + résumé statistique des anomalies avec méthode/paramètres + les 10 anomalies aux scores les plus extrêmes + statistiques des visualisations). Le prompt système impose explicitement au LLM de distinguer une anomalie statistique (isolable selon le modèle) d'une anomalie métier (erreur, fraude, donnée pathologique) — vérifiable en relisant le texte du prompt système
5. *(révisé, correction #1 V2.1)* Sur un appel LLM réussi, la réponse respecte le contrat de sortie (ADR-7) : `resume` non vide, au moins 1 `recommandation`, et un nombre d'`insights` **justifié par la richesse analytique disponible** plutôt qu'un chiffre imposé — cible de 3 insights minimum lorsque le rapport qualité + les résultats d'anomalies + les statistiques de visualisations fournis dans le prompt permettent d'en produire 3 de façon rattachable à une donnée réelle (critère 6) ; en dessous, un nombre inférieur est acceptable **à condition qu'aucun insight ne soit inventé** pour atteindre un quota. Chaque insight présent doit avoir `titre`, `description`, `importance`, `source` non vides
6. *(révisé, correction #2 V2.1)* Chaque `source` d'insight est un objet structuré conforme au contrat (`type`, `element`, `metrique`, `valeur`) et la `valeur` correspond bien à un résultat effectivement présent dans le prompt envoyé pour l'`element`/`metrique` cités (vérifiable par recoupement automatique champ par champ, plus fiable qu'une recherche de sous-chaîne dans du texte libre)
7. Si la clé API est absente ou invalide, le moteur retourne un JSON avec `{"erreur": "..."}` dans la section insights, sans lever d'exception ; les sections qualité/profil/anomalies/visualisations restent présentes et correctes
8. Le JSON final combine bien les 4 blocs : qualité (Milestone 1, inchangé), anomalies, visualisations, insights IA
9. Aucune clé API n'apparaît dans le JSON de sortie ni dans les logs
10. Aucune modification n'est détectée dans `backend/qualite_donnees/` (le Milestone 1 reste intact)
11. *(nouveau, correction #3 V2.1)* Deux exécutions successives d'`anomalies.py` sur le même dataset (même fichier, non modifié) produisent exactement les mêmes scores d'anomalie pour chaque observation — vérifie que le `random_state` fixe (ADR-1) rend Isolation Forest réellement reproductible
12. *(nouveau, correction #4 V2.1)* Sur le dataset énergie (~2M lignes), le pipeline mesure et journalise explicitement (et non suppose) : le temps de chargement du CSV, le temps de construction de l'artefact analytique, l'usage mémoire, le temps d'exécution d'Isolation Forest, et le temps de génération des visualisations — ces mesures sont présentes dans la sortie ou les logs, avec des valeurs cohérentes (aucune ne doit être nulle, absente, ou anormalement élevée au point de rendre le pipeline inutilisable en pratique)

## Responsable exécution

- Spécification V1 : Claude → NO-GO conditionnel ChatGPT/DILANE (incohérence artefact analytique) → V2 : Claude → quasi-GO ChatGPT (architecture validée, 4 ajustements demandés) → V2.1 (ce document) : Claude → **VALIDÉ par DILANE**
- Implémentation : Claude — en cours, tâche par tâche
- Tests contre les critères ci-dessus : Claude Code (en boîte noire, sans lire `insights_ia/`)
- Validation finale : DILANE
