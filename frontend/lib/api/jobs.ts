/**
 * lib/api/jobs.ts — GET /api/v1/jobs/{job_id} (Milestone #5, tâche #4).
 */

import { requeteJson } from "@/lib/api/client";
import type { JobPublic } from "@/lib/types";

export async function obtenirJob(jobId: string): Promise<JobPublic> {
  const { corps } = await requeteJson<JobPublic>(`/jobs/${jobId}`);
  return corps;
}
