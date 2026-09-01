/**
 * lib/api/certifications.ts — POST /api/v1/certifications (Milestone #5, tâche #7).
 *
 * Contrat vérifié directement dans routes/certifications.py (pas supposé) : multipart/form-data
 * avec les champs "fichier", "owner_address", "version" (optionnel, défaut 1 — non exposé dans
 * l'UI pour ce Milestone, aucun wireframe de la spec ne le demande). L'idempotence à 3 cas
 * (ADR-5) répond sur DEUX codes HTTP différents avec DEUX formes de corps différentes :
 *
 *   - 200, cas (a) "termine"   : le résultat de certification directement (ResultatCertification),
 *                                aucun job créé — un certificat existait déjà pour ce hash.
 *   - 200, cas (b) "en_cours"  : {"job_id", "statut"} — un job en_attente/en_cours existait déjà.
 *   - 202, cas (c)/nouveau     : {"job_id", "statut"} — nouveau job créé, à suivre par polling.
 *
 * Les cas (b) et (c) ont la même forme de corps et se traitent identiquement côté UI (les deux
 * mènent à un job à suivre) — seul le cas (a) est structurellement différent (pas de job_id).
 * On distingue donc les deux formes par la présence de "job_id" dans le corps, pas par le code
 * HTTP seul (ADR-9-bis appliqué ici : distinguer par la forme réelle des données, pas par
 * hypothèse sur le code de statut).
 */

import { requeteMultipart } from "@/lib/api/client";
import type { JobCree, ResultatCertification } from "@/lib/types";

export type ReponseCertification =
  | { type: "resultat_direct"; resultat: ResultatCertification }
  | { type: "job"; job: JobCree };

function estJobCree(corps: ResultatCertification | JobCree): corps is JobCree {
  return "job_id" in corps;
}

export async function certifierDataset(
  fichier: File,
  ownerAddress: string,
  version = 1,
): Promise<ReponseCertification> {
  const corpsFormulaire = new FormData();
  corpsFormulaire.append("fichier", fichier);
  corpsFormulaire.append("owner_address", ownerAddress);
  corpsFormulaire.append("version", String(version));

  const { corps } = await requeteMultipart<ResultatCertification | JobCree>(
    "/certifications",
    corpsFormulaire,
  );

  if (estJobCree(corps)) {
    return { type: "job", job: corps };
  }
  return { type: "resultat_direct", resultat: corps };
}
