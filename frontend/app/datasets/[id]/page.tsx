/**
 * Page de détail d'un dataset certifié (tâche #10) — certificat + qualité + insights (via
 * GET /api/v1/datasets/{id}, Milestone #4.1) + vérification d'intégrité.
 *
 * Server component délibérément minimal : `id` (dataset_id on-chain, entier auto-incrémenté par
 * le contrat — ADR-7 du Milestone #3) est extrait et validé ici, le contenu réel délégué à
 * DetailDataset ("use client", components/datasets/detail-dataset.tsx).
 */

import { DetailDataset } from "@/components/datasets/detail-dataset";

export default async function DatasetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const datasetId = Number(id);

  if (!Number.isInteger(datasetId) || datasetId < 0) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-16 text-center">
        <h1 className="text-xl font-semibold">Identifiant invalide</h1>
        <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
          « {id} » n’est pas un identifiant de dataset valide.
        </p>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col items-center p-4">
      <DetailDataset datasetId={datasetId} />
    </main>
  );
}
