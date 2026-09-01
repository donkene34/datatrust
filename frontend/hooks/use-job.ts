"use client";

/**
 * hooks/use-job.ts (Milestone #5, tâche #4).
 *
 * Polling TanStack Query (2s, arrêt sur statut terminal) + persistance du job_id dans l'URL
 * (query param dédié par type de job — "qualite" | "insights" | "certification", V3 §3 de la
 * spec) : un refresh de /depot pendant un job en cours ne perd pas son suivi, et jusqu'à 3 jobs
 * (qualité, insights, certification) peuvent coexister dans l'URL de la même page.
 *
 * demarrerJob() est appelé par les composants après la création d'un nouveau job (ex. après
 * deposerQualite()) — il met à jour l'URL, ce qui déclenche automatiquement le polling puisque
 * le job_id devient non-null.
 *
 * CONTRAINTE VÉRIFIÉE (build réel) : useSearchParams() exige que le composant qui appelle ce
 * hook soit enveloppé dans un <Suspense> — sinon `next build` échoue avec "useSearchParams()
 * should be wrapped in a suspense boundary". La page qui utilise useJob() (ex. /depot, tâche #5)
 * doit donc être structurée ainsi :
 *   // app/depot/page.tsx (server component, pas de "use client")
 *   export default function DepotPage() {
 *     return <Suspense fallback={...}><DepotContenu /></Suspense>;
 *   }
 *   // DepotContenu (dans un fichier séparé, "use client") appelle useJob() normalement.
 */

import { useCallback } from "react";
import { useQuery, type Query } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { obtenirJob } from "@/lib/api/jobs";
import type { ErreurJob, JobPublic, StatutJob } from "@/lib/types";

export type ParametreJob = "qualite" | "insights" | "certification";

const STATUTS_ACTIFS: StatutJob[] = ["en_attente", "en_cours"];

const INTERVALLE_POLLING_MS = 2000;

export interface UseJobResultat {
  /** job_id actuellement suivi pour ce paramètre (lu depuis l'URL), ou null si aucun job. */
  jobId: string | null;
  job: JobPublic | undefined;
  chargement: boolean;
  enCours: boolean;
  termine: boolean;
  /** true pour "echec" ET "echec_recuperable" — les deux sont des états terminaux côté UI. */
  echec: boolean;
  /** Détail de l'échec métier (job.erreur), distinct d'une erreur de la requête HTTP elle-même. */
  erreurJob: ErreurJob | null;
  erreurRequete: Error | null;
  /** À appeler après la création d'un nouveau job pour ce paramètre — met à jour l'URL et
   * démarre le polling. */
  demarrerJob: (nouveauJobId: string) => void;
  /** Retire ce paramètre de l'URL (retour à l'état "aucun job") — utilisé par le bouton
   * "réessayer" après un échec (V3 §7 de la spec : qualité/insights se relancent par un nouvel
   * upload/appel, pas par retry sur le job existant). Ajouté en tâche #5, en construisant la
   * page /depot — la gestion de l'URL reste la responsabilité de ce hook, pas des composants. */
  reinitialiser: () => void;
}

export function useJob(parametre: ParametreJob): UseJobResultat {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const jobId = searchParams.get(parametre);

  const requete = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => obtenirJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (requeteEnCours: Query<JobPublic>) => {
      const statut = requeteEnCours.state.data?.statut;
      if (!statut) {
        // Pas encore de première réponse : on continue de sonder plutôt que de supposer.
        return INTERVALLE_POLLING_MS;
      }
      return STATUTS_ACTIFS.includes(statut) ? INTERVALLE_POLLING_MS : false;
    },
  });

  const demarrerJob = useCallback(
    (nouveauJobId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set(parametre, nouveauJobId);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [parametre, pathname, router, searchParams],
  );

  const reinitialiser = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete(parametre);
    const chaineParams = params.toString();
    router.replace(chaineParams ? `${pathname}?${chaineParams}` : pathname, { scroll: false });
  }, [parametre, pathname, router, searchParams]);

  const statut = requete.data?.statut;

  return {
    jobId,
    job: requete.data,
    chargement: requete.isLoading,
    enCours: !!statut && STATUTS_ACTIFS.includes(statut),
    termine: statut === "termine",
    echec: statut === "echec" || statut === "echec_recuperable",
    erreurJob: requete.data?.erreur ?? null,
    erreurRequete: requete.error instanceof Error ? requete.error : null,
    demarrerJob,
    reinitialiser,
  };
}
