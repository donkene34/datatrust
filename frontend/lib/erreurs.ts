/**
 * lib/erreurs.ts — mapping centralisé code d'erreur backend → message humain (Milestone #5,
 * tâche #8).
 *
 * Deux surfaces d'erreur distinctes dans cette app, toutes deux mappées ici à partir du même
 * dictionnaire de codes (les mêmes codes peuvent apparaître sur l'une ou l'autre selon où
 * l'échec survient) :
 * - `ErreurApi` (lib/api/client.ts) : la requête HTTP elle-même échoue immédiatement (4xx/5xx,
 *   avant même la création d'un job) — levée par requeteJson()/requeteMultipart().
 * - `ErreurJob` (lib/types.ts) : un job créé avec succès (202/200) passe ensuite au statut
 *   "echec" en cours de traitement asynchrone — lu via le polling de hooks/use-job.ts.
 *
 * Tous les codes ci-dessous sont vérifiés directement dans le code source backend (pas
 * supposés) : routes/qualite.py, routes/insights.py, routes/certifications.py,
 * jobs/gestionnaire.py (dont le cas particulier de "echec_recuperable" sans code, voir
 * traduireErreurJob ci-dessous).
 */

import { ErreurApi } from "@/lib/api/client";
import type { ErreurJob } from "@/lib/types";

const MESSAGES_PAR_CODE: Record<string, string> = {
  // --- Erreurs de requête HTTP (4xx immédiat, avant création de job) ---
  fichier_absent: "Aucun fichier n'a été reçu — sélectionnez un fichier avant de continuer.",
  fichier_invalide: "Le fichier envoyé est vide ou illisible.",
  job_introuvable:
    "Le job référencé est introuvable — il a peut-être expiré ou son identifiant est incorrect.",
  type_job_incorrect: "Ce job n'est pas du type attendu pour cette opération.",
  job_qualite_non_termine:
    "Le rapport qualité associé n'est pas encore terminé — patientez avant de lancer l'analyse IA.",
  dataset_incoherent:
    "Le fichier source a changé ou est devenu introuvable depuis le calcul du rapport qualité — redéposez le fichier pour relancer l'analyse.",
  dataset_introuvable: "Aucun certificat trouvé pour ce dataset.",
  erreur_inconnue: "Réponse inattendue du serveur.",

  // --- Erreurs de job (statut "echec", survenues pendant le traitement en arrière-plan) ---
  rapport_qualite_echec:
    "L'analyse qualité a échoué — le fichier est peut-être mal formé ou dans un format inattendu.",
  rapport_intelligence_echec: "L'analyse IA a échoué.",
  certification_echec: "La certification a échoué.",
  upload_ipfs_echec: "L'enregistrement du fichier sur IPFS a échoué.",
  transaction_blockchain_echec: "La transaction blockchain a échoué ou a été rejetée.",
};

const MESSAGE_PAR_DEFAUT = "Une erreur inattendue est survenue.";

/** Traduit une ErreurApi (échec de la requête HTTP elle-même) en message humain à afficher. */
export function traduireErreurApi(erreur: ErreurApi): string {
  return MESSAGES_PAR_CODE[erreur.code] ?? erreur.message ?? MESSAGE_PAR_DEFAUT;
}

/** Traduit l'erreur d'un job (job.erreur, lu via le polling) en message humain à afficher.
 * `erreurJob` est `null` pour un job "echec_recuperable" né d'une réconciliation au démarrage du
 * serveur (jobs/gestionnaire.py::reconcilier_au_demarrage) — ce cas ne renseigne délibérément
 * aucun ErreurJob puisqu'il ne s'agit pas d'un échec métier identifié, seulement d'une
 * interruption ; message dédié plutôt qu'un message par défaut trompeur. */
export function traduireErreurJob(erreurJob: ErreurJob | null): string {
  if (!erreurJob) {
    return "Le traitement a été interrompu (probablement un redémarrage du serveur) — relancez-le.";
  }
  return MESSAGES_PAR_CODE[erreurJob.code] ?? erreurJob.message ?? MESSAGE_PAR_DEFAUT;
}

/** Traduit n'importe quelle erreur JS attrapée dans un try/catch en message humain — pour les
 * points d'appel (gererDepot, gererAnalyseIA, gererConfirmerCertification) qui ne savent pas a
 * priori si l'erreur reçue est une ErreurApi structurée ou une Error générique (ex. réseau
 * indisponible, fetch qui échoue avant même d'atteindre le serveur). */
export function traduireErreurInconnue(erreur: unknown): string {
  if (erreur instanceof ErreurApi) return traduireErreurApi(erreur);
  if (erreur instanceof Error) return erreur.message;
  return MESSAGE_PAR_DEFAUT;
}
