/**
 * lib/api/datasets.ts — GET /api/v1/datasets/{id} et POST /api/v1/certifications/{id}/verifier
 * (Milestone #5, tâche #10).
 *
 * obtenirDataset() : nouvel endpoint du Milestone #4.1 (V3 §1.5 de la spec) — un seul aller-retour
 * pour peupler /datasets/[id] avec certificat + qualité + insights liés, de façon identique pour
 * tout visiteur (promesse "Data Trust" : contrairement aux job_id qualité/insights/certification,
 * qui ne survivent que dans l'URL de /depot d'un navigateur donné, cette page doit fonctionner
 * pour n'importe qui ouvre le lien).
 *
 * verifierIntegrite() : endpoint synchrone déjà existant du Milestone #4 (routes/certifications.py)
 * — aucun job créé, upload d'un fichier comparé immédiatement au certificat déjà on-chain pour ce
 * dataset_id.
 */

import { requeteJson, requeteMultipart } from "@/lib/api/client";
import type { DatasetComplet, ResultatVerification } from "@/lib/types";

export async function obtenirDataset(datasetId: number): Promise<DatasetComplet> {
  const { corps } = await requeteJson<DatasetComplet>(`/datasets/${datasetId}`);
  return corps;
}

export async function verifierIntegrite(
  datasetId: number,
  fichier: File,
): Promise<ResultatVerification> {
  const corpsFormulaire = new FormData();
  corpsFormulaire.append("fichier", fichier);
  const { corps } = await requeteMultipart<ResultatVerification>(
    `/certifications/${datasetId}/verifier`,
    corpsFormulaire,
  );
  return corps;
}
