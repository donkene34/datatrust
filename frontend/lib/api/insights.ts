/**
 * lib/api/insights.ts — POST /api/v1/insights/rapports (Milestone #5, tâche #6).
 *
 * Corps JSON {"job_id"} référençant un job "rapport_qualite" déjà terminé (ADR-9-bis) — jamais
 * d'upload direct ici, vérifié dans routes/insights.py. Erreurs possibles : 404 job_introuvable,
 * 400 type_job_incorrect, 409 job_qualite_non_termine, 409 dataset_incoherent — toutes gérées
 * de façon générique par ErreurApi (lib/api/client.ts) et traduites en tâche #8.
 */

import { requeteJson } from "@/lib/api/client";
import type { JobCree } from "@/lib/types";

export async function lancerInsights(jobIdQualite: string): Promise<JobCree> {
  const { corps } = await requeteJson<JobCree>("/insights/rapports", {
    method: "POST",
    body: JSON.stringify({ job_id: jobIdQualite }),
  });
  return corps;
}
