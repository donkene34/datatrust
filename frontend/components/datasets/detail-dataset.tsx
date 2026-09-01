"use client";

/**
 * components/datasets/detail-dataset.tsx (Milestone #5, tâche #10).
 *
 * Contenu réel de /datasets/[id] (V2 §8, mis à jour par V3 §1.7 : un seul appel à
 * GET /api/v1/datasets/{id} — Milestone #4.1 — au lieu de la limite ouverte de la V2). Simple
 * fetch ponctuel (pas de polling, pas de job) : useQuery directement ici plutôt qu'un hook dédié,
 * contrairement à hooks/use-job.ts qui, lui, justifie son existence par la logique de polling +
 * persistance d'URL partagée entre 3 types de jobs.
 *
 * Pas de useSearchParams ici (l'identifiant vient du segment de route, pas de la query string) :
 * contrairement à DepotContenu, ce composant n'a donc pas besoin d'un <Suspense> autour de lui
 * pour cette raison — app/datasets/[id]/page.tsx reste néanmoins un server component séparé, par
 * cohérence avec le reste de l'app plutôt que par nécessité technique ici.
 */

import { useQuery } from "@tanstack/react-query";

import { CertificatAffichage } from "@/components/certification/certificat-affichage";
import { VerificationIntegrite } from "@/components/certification/verification-integrite";
import { RapportInsightsAffichage } from "@/components/insights/rapport-insights";
import { RapportQualiteAffichage } from "@/components/qualite/rapport-qualite";
import { obtenirDataset } from "@/lib/api/datasets";
import { traduireErreurInconnue } from "@/lib/erreurs";

export function DetailDataset({ datasetId }: { datasetId: number }) {
  const {
    data: dataset,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => obtenirDataset(datasetId),
  });

  if (isLoading) {
    return <p className="p-8 text-sm text-zinc-500">Chargement…</p>;
  }

  if (isError || !dataset) {
    return (
      <div className="flex flex-col items-center gap-2 p-8 text-center">
        <p className="text-red-600">{traduireErreurInconnue(error)}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-6 p-8">
      <h1 className="text-xl font-semibold">Dataset #{dataset.dataset_id}</h1>

      <CertificatAffichage certificat={dataset.certificat} />

      {dataset.qualite ? (
        <RapportQualiteAffichage rapport={dataset.qualite} />
      ) : (
        <p className="text-sm text-zinc-500">
          Aucun rapport qualité lié n’a été retrouvé pour ce dataset.
        </p>
      )}

      {dataset.insights ? (
        <RapportInsightsAffichage rapport={dataset.insights} />
      ) : (
        <p className="text-sm text-zinc-500">
          Aucune analyse IA liée n’a été retrouvée pour ce dataset.
        </p>
      )}

      <VerificationIntegrite datasetId={dataset.dataset_id} />
    </div>
  );
}
