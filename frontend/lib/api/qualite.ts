/**
 * lib/api/qualite.ts — POST /api/v1/qualite/rapports (Milestone #5, tâche #5).
 *
 * Champ multipart "fichier" — nom exact attendu par routes/qualite.py côté backend
 * (`fichier: UploadFile = File(...)`), vérifié dans le code source, pas supposé.
 */

import { requeteMultipart } from "@/lib/api/client";
import type { JobCree } from "@/lib/types";

export async function deposerQualite(fichier: File): Promise<JobCree> {
  const corpsFormulaire = new FormData();
  corpsFormulaire.append("fichier", fichier);
  const { corps } = await requeteMultipart<JobCree>("/qualite/rapports", corpsFormulaire);
  return corps;
}
