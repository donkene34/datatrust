/**
 * lib/types.ts — types TypeScript miroir des schémas Pydantic du backend
 * (Milestone #5, tâche #3).
 *
 * Sources de vérité pour ces contrats :
 * - Enveloppe Job, endpoints, codes d'erreur : docs/milestone_4_api.md (V3, figée).
 * - Rapport qualité (`RapportQualite`) : docs/milestone_1_coeur_data.md § "Contrat de données".
 * - Rapport intelligence (`RapportInsights`) : docs/milestone_2_intelligence.md § "Contrat de
 *   sortie du LLM" + critère d'acceptation #8 (4 blocs : qualité, anomalies, visualisations,
 *   insights IA) — la clé top-niveau "insights_ia" est confirmée par une sortie réelle observée
 *   pendant les tests du Milestone #4 (`{"insights_ia": {"erreur": "Quota Groq..."}}`).
 * - Certificat / résultat de certification : payload réel observé lors des tests boîte noire du
 *   Milestone #4 (vraie transaction Sepolia, dataset_id 11).
 *
 * Les types "resultat" (RapportQualite, RapportInsights, ResultatCertification) sont volontairement
 * ouverts (`[cle: string]: unknown` en bas de chaque interface) plutôt que fermés strictement :
 * le contrat exact de qualite_donnees/insights_ia n'a pas été revérifié champ par champ depuis le
 * frontend (voir aussi V3 §10 de la spec Milestone #5 — la précision totale de ces schémas n'est
 * pas garantie). Mieux vaut un type permissif qu'un type qui ment sur sa propre exhaustivité.
 */

export type TypeJob = "rapport_qualite" | "rapport_intelligence" | "certification";

export type StatutJob = "en_attente" | "en_cours" | "termine" | "echec" | "echec_recuperable";

export interface ErreurJob {
  code: string;
  message: string;
}

/** Réponse de GET /api/v1/jobs/{job_id} — champs internes (chemin_fichier_temp, dataset_hash,
 * transaction_hash) jamais exposés par l'API, donc absents ici aussi. */
export interface JobPublic {
  job_id: string;
  type: TypeJob;
  statut: StatutJob;
  progression: number | null;
  etape: string | null;
  resultat: Record<string, unknown> | null;
  erreur: ErreurJob | null;
  cree_le: string;
  mis_a_jour_le: string;
}

/** Format uniforme de toute réponse 4xx/5xx (milestone_4_api.md § "Gestion des erreurs"). */
export interface ErreurApiPayload {
  erreur: ErreurJob;
}

/** Réponse 202 (nouveau job créé). */
export interface JobCree {
  job_id: string;
  statut: StatutJob;
}

// --- Rapport qualité (Milestone #1) ---

export interface DimensionQualite {
  score: number;
  statut: "evalue" | "non_applicable";
  explication: string;
  details: Record<string, unknown>;
}

export interface ScoresDimensions {
  completude: DimensionQualite;
  coherence: DimensionQualite;
  unicite: DimensionQualite;
  validite: DimensionQualite;
  aberrations: DimensionQualite;
  fraicheur: DimensionQualite;
}

export interface ColonneProfil {
  nom: string;
  type: string;
  nb_manquants: number;
  taux_manquants: number;
  nb_valeurs_uniques: number;
  min: number | null;
  max: number | null;
  moyenne: number | null;
  ecart_type: number | null;
}

export interface CorrelationProfil {
  colonne_a: string;
  colonne_b: string;
  coefficient: number;
}

export interface ProfilDataset {
  jeu_de_donnees: string;
  taille: { lignes: number; colonnes: number };
  colonnes: ColonneProfil[];
  correlations: CorrelationProfil[];
}

/** resultat d'un job de type "rapport_qualite" une fois "termine". */
export interface RapportQualite {
  jeu_de_donnees: string;
  separateur_detecte: string;
  score_global: number;
  scores_dimensions: ScoresDimensions;
  profil: ProfilDataset;
  [cle: string]: unknown;
}

// --- Rapport intelligence (Milestone #2) ---

export interface SourceInsight {
  type: "statistique" | "anomalie" | "correlation";
  element: string;
  metrique: string;
  valeur: number;
}

export interface Insight {
  titre: string;
  description: string;
  importance: "elevee" | "moyenne" | "faible";
  source: SourceInsight;
}

export interface Recommandation {
  titre: string;
  description: string;
}

/** insights_ia peut être soit le résultat LLM normal, soit {"erreur": "..."} en dégradation
 * gracieuse (clé Groq absente/invalide/quota dépassé) — les deux formes sont légitimes. */
export type BlocInsightsIA =
  | { resume: string; insights: Insight[]; recommandations: Recommandation[] }
  | { erreur: string };

/** resultat d'un job de type "rapport_intelligence" une fois "termine". Combine qualité
 * (inchangée), anomalies, visualisations et insights IA (critère #8, milestone_2_intelligence.md). */
export interface RapportInsights {
  insights_ia: BlocInsightsIA;
  [cle: string]: unknown;
}

// --- Certification / certificat (Milestone #3, exposé par le Milestone #4) ---

/** Champs on-chain purs — struct DatasetCertificate du contrat Solidity, plus dataset_id.
 * C'est la forme de GET /api/v1/certifications/{dataset_id} et du champ "certificat" de
 * GET /api/v1/datasets/{dataset_id}. */
export interface Certificat {
  dataset_id: number;
  owner: string;
  certifier: string;
  dataset_hash: string;
  ipfs_cid: string;
  metadata_hash: string;
  version: number;
  quality_score: number;
  timestamp: number;
}

/** resultat d'un job de type "certification" une fois "termine" — le certificat on-chain
 * (ci-dessus) plus les métadonnées et mesures propres à CETTE exécution de certification. */
export interface ResultatCertification extends Certificat {
  metadonnees: {
    nom_fichier: string;
    score_global: number;
    scores_dimensions: ScoresDimensions;
    date_certification: string;
  };
  hash_transaction: string;
  gas_utilise: number;
  cout_eth: number;
  mesures_temps: Record<string, number>;
  temps_total_secondes: number;
}

/** Réponse de POST /api/v1/certifications/{dataset_id}/verifier (synchrone). */
export interface ResultatVerification {
  identique: boolean;
  dataset_id: number;
  hash_recalcule: string;
  hash_certifie: string;
}

/** Réponse de GET /api/v1/datasets/{dataset_id} (Milestone #4.1). qualite/insights sont null
 * quand aucun job correspondant n'a été retrouvé pour ce dataset — cas légitime, pas une erreur. */
export interface DatasetComplet {
  dataset_id: number;
  certificat: Certificat;
  qualite: RapportQualite | null;
  insights: RapportInsights | null;
}
