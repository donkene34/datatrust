# Milestone #1 — Phase 1 : Cœur Data
## Spécification V3 — implémentée, testée, JSON entièrement en français

**Statut :** V3 — implémentation livrée et testée sur 4/5 datasets. Le changement V2 → V3 (noms de variables et clés JSON en français) est une demande explicite de DILANE, **à relayer à ChatGPT pour information** : le contrat JSON qu'il avait validé en V2 a changé de noms de clés (aucun changement de sémantique/logique).

**Historique :** V1 proposée par Claude → GO conditionnel de ChatGPT/DILANE sur 3 points (validity, freshness, profiler) → V2 intègre ces 3 points, validée → V3 : DILANE demande que toutes les variables Python ET les clés du JSON produit soient en français.

---

## Objectif

Construire le Data Quality Engine : à partir d'un fichier CSV, produire un profilage statistique complet et un Data Quality Score multidimensionnel explicable, testé sur les 5 datasets de démonstration.

## Architecture (noms de fichiers francisés en V3, demande DILANE)

```
backend/
├── qualite_donnees/
│   ├── __init__.py
│   ├── chargeur.py          # chargement CSV → tableau Pandas, détection encodage/séparateur
│   ├── profileur.py         # profilage statistique (types, distributions, stats descriptives)
│   ├── utilitaires_type.py  # détection robuste du type textuel (compat. Pandas 2.x/3.x)
│   ├── dimensions/
│   │   ├── completude.py      # complétude
│   │   ├── coherence.py       # cohérence des types/formats
│   │   ├── unicite.py         # doublons
│   │   ├── validite.py        # valeurs hors règles automatiquement inférables
│   │   ├── aberrations.py     # anomalies statistiques
│   │   └── fraicheur.py       # fraîcheur temporelle (si colonne date détectée)
│   ├── notation.py          # agrégation pondérée → score global + détail par dimension
│   └── rapport.py           # génère le rapport structuré (JSON) : score + explications textuelles
├── lancer_rapports.py     # script de démonstration sur les datasets du dossier dataset/
└── tests/                 # (Claude Code — non rempli par moi)
```

*(les modules ont d'abord été livrés en anglais (`data_quality/`, `loader.py`, etc.), puis intégralement renommés en français sur demande explicite de DILANE — même logique, mêmes tests, seuls les noms changent)*

**Flux :**
```
CSV → chargeur.py → tableau Pandas
    → profileur.py → profil structuré complet (contrat de données, voir ci-dessous)
    → dimensions/*.py → un score par dimension (0-100) + statut + détails
    → notation.py → score global pondéré + rapport par dimension
    → rapport.py → JSON structuré : {score_global, scores_dimensions, explications, profil}
```

## Contrat de données — `profileur.py` (point d'arbitrage #3, noms francisés en V3)

`profileur.py` ne se contente pas d'afficher des statistiques : il produit une structure exploitable par la Phase 2 (AI Insights Engine) et par les dimensions elles-mêmes.

```json
{
  "jeu_de_donnees": "nom_du_fichier.csv",
  "taille": { "lignes": 0, "colonnes": 0 },
  "colonnes": [
    {
      "nom": "nom_colonne",
      "type": "int64 | float64 | str | datetime64 | bool",
      "nb_manquants": 0,
      "taux_manquants": 0.0,
      "nb_valeurs_uniques": 0,
      "min": null,
      "max": null,
      "moyenne": null,
      "ecart_type": null
    }
  ],
  "correlations": [
    { "colonne_a": "col1", "colonne_b": "col2", "coefficient": 0.0 }
  ]
}
```

- `min`/`max`/`moyenne`/`ecart_type` sont calculés uniquement pour les colonnes numériques (`null` sinon)
- `correlations` ne concerne que les paires de colonnes numériques (corrélation de Pearson)
- Ce contrat est la sortie unique de `profileur.py` ; toutes les dimensions le consomment plutôt que de recalculer leurs propres statistiques de base

**Rapport final (`rapport.py`)** — mêmes principes, clés françaises :
```json
{
  "jeu_de_donnees": "...",
  "separateur_detecte": ",",
  "score_global": 0.0,
  "scores_dimensions": {
    "completude": { "score": 0.0, "statut": "evalue | non_applicable", "explication": "...", "details": {} },
    "coherence": { "...": "..." },
    "unicite": { "...": "..." },
    "validite": { "...": "..." },
    "aberrations": { "...": "..." },
    "fraicheur": { "...": "..." }
  },
  "profil": { "...": "voir contrat profileur.py ci-dessus" }
}
```

Le champ `status` devient `statut`, avec les valeurs `evaluated` → `evalue` et `not_applicable` → `non_applicable`. Le nom de la dimension "outliers" devient `aberrations` dans les clés du JSON.

## Décisions (ADR)

| # | Décision | Justification |
|---|---|---|
| ADR-1 | Chargement CSV via Pandas, détection automatique du séparateur (`,` `;` `\t`) | Nos 5 datasets utilisent des séparateurs différents (ex. `;` pour le dataset énergie) |
| ADR-2 | Pondération par défaut égale entre les 6 dimensions (≈16,7 % chacune), configurable ensuite | Évite un biais arbitraire au démarrage ; ajustable après tests sur les 5 datasets |
| ADR-3 *(révisé)* | La dimension "fraîcheur" retourne `{"score": 100, "status": "not_applicable"}` si aucune colonne date n'est détectée — jamais un score "muet" identique à un vrai résultat évalué | Point d'arbitrage #2 : un dataset sans dimension temporelle ne doit pas apparaître comme "excellent en fraîcheur" — la distinction `not_applicable` vs `evaluated` est obligatoire pour la rigueur du rapport |
| ADR-4 | Détection d'outliers via IQR (écart interquartile) pour cette phase, pas de modèle ML dédié | Suffisant et interprétable pour la Phase 1 ; une détection plus fine (isolation forest, etc.) pourra être ajoutée en Phase 2 si besoin |
| ADR-5 | Sortie systématiquement en JSON structuré, jamais de texte libre à ce stade | L'AI Insights Engine (Phase 2) doit consommer des résultats structurés, pas du texte |
| ADR-6 *(nouveau)* | `validite.py` est strictement limité aux règles automatiquement inférables — pas de règles métier nécessitant une connaissance du domaine | Point d'arbitrage #1 : le moteur ne peut pas savoir qu'un `age = -15` est invalide sans connaître le domaine métier ; les règles personnalisées sont une évolution hors MVP |

### Périmètre exact de `validite.py` (ADR-6)

Uniquement des règles détectables automatiquement, sans connaissance métier :
- conformité au type inféré par colonne (une valeur texte dans une colonne majoritairement numérique)
- dates invalides (format incohérent ou date impossible, ex. `32/13/2020`)
- valeurs infinies (`inf`, `-inf`)
- valeurs numériques "déguisées" en texte (`"NaN"`, `"null"`, `"N/A"` non reconnues comme valeurs manquantes par le loader)
- formats internes incohérents au sein d'une même colonne (ex. mélange de formats de date `JJ/MM/AAAA` et `AAAA-MM-JJ` dans la même colonne)
- valeurs incompatibles avec le type de la colonne une fois ce type inféré par `profileur.py`

Explicitement **hors périmètre** pour le MVP : toute règle nécessitant une connaissance du domaine (ex. "un âge ne peut pas être négatif", "un email doit être valide"). Ces règles métier personnalisables pourront être ajoutées après le MVP, potentiellement via un fichier de configuration optionnel.

## Contraintes

- Respecte le cadrage MVP figé : CSV uniquement, pas d'autre format
- Aucune donnée brute ne doit être modifiée sur disque — le profilage est en lecture seule
- Le code doit fonctionner sur les 5 datasets de démonstration sans erreur, malgré leurs différences (séparateurs, encodages, présence/absence de colonnes date)
- Chaque dimension doit retourner : un score numérique (0-100) ET une explication textuelle des faiblesses détectées (pas de score "muet")

## Critères d'acceptation (pour Claude Code)

1. Le loader charge correctement les 5 CSV de démonstration sans erreur, quel que soit leur séparateur
2. Chaque dimension (`completude`, `coherence`, `unicite`, `validite`, `aberrations`, `fraicheur`) retourne un score entre 0 et 100 pour chacun des 5 datasets
3. Le score global est bien la moyenne pondérée des 6 scores de dimension (vérifiable par calcul indépendant)
4. Pour un dataset dont on a injecté volontairement des valeurs manquantes connues, le score de complétude reflète bien le taux réel de valeurs manquantes (tolérance ±1 point)
5. Le rapport JSON produit contient, pour chaque dimension, un champ `score` (numérique) et un champ `explication` (texte non vide)
6. Aucune exception non gérée ne doit survenir sur les 5 datasets, même avec des colonnes 100 % vides ou un dataset sans aucune valeur manquante
7. `profileur.py` retourne bien le contrat de données complet (`jeu_de_donnees`, `taille`, `colonnes[]` avec tous les champs, `correlations[]`) pour les 5 datasets
8. Sur un dataset sans colonne date détectable, la dimension `fraicheur` retourne exactement `{"score": 100, "statut": "non_applicable", ...}` — le champ `statut` doit être présent et distinct de `"evalue"`
9. Sur un dataset avec colonne date valide, la dimension `fraicheur` retourne `"statut": "evalue"` avec un score reflétant réellement la pertinence temporelle
10. `validite.py` ne signale aucune erreur sur des valeurs métier légitimes mais statistiquement inhabituelles (ex. un âge de 95 ans ne doit pas être signalé invalide) — seules les règles listées dans ADR-6 doivent déclencher un signalement

## Responsable exécution

- Spécification V1 : Claude → arbitrage ChatGPT/DILANE sur 3 points → V2 : Claude → validée
- V2 → V3 : francisation complète des variables et du JSON (demande DILANE) → implémentée et testée par Claude
- Implémentation : Claude — testée sur 4/5 datasets (santé, immobilier, RH, finance ; énergie manquant, pas encore téléchargé)
- Prochaine étape : relayer la V3 à ChatGPT pour information (changement de noms de clés uniquement, aucun changement de logique/architecture)
- Tests contre les critères ci-dessus : Claude Code (en boîte noire, sans lire `qualite_donnees/`)
- Validation finale du milestone : DILANE
