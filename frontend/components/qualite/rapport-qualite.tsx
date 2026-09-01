/**
 * components/qualite/rapport-qualite.tsx (Milestone #5, tâche #5).
 *
 * Composant de présentation pur (pas de "use client" : aucun state, aucun hook) — affiche un
 * RapportQualite déjà résolu. Réutilisable tel quel sur /depot (tâche #5) et sur la page de
 * détail /datasets/[id] (tâche #10), qui affichera le même type de rapport.
 */

import type { DimensionQualite, RapportQualite } from "@/lib/types";

const LIBELLES_DIMENSIONS: Record<string, string> = {
  completude: "Complétude",
  coherence: "Cohérence",
  unicite: "Unicité",
  validite: "Validité",
  aberrations: "Aberrations",
  fraicheur: "Fraîcheur",
};

function CarteDimension({ cle, dimension }: { cle: string; dimension: DimensionQualite }) {
  const nonApplicable = dimension.statut === "non_applicable";
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
        {LIBELLES_DIMENSIONS[cle] ?? cle}
      </p>
      <p className="text-lg font-semibold">{nonApplicable ? "N/A" : dimension.score.toFixed(0)}</p>
      {!nonApplicable && (
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{dimension.explication}</p>
      )}
    </div>
  );
}

export function RapportQualiteAffichage({ rapport }: { rapport: RapportQualite }) {
  const dimensions = Object.entries(rapport.scores_dimensions) as [string, DimensionQualite][];

  return (
    <div className="w-full max-w-2xl space-y-6">
      <div className="text-center">
        <p className="text-sm text-zinc-500">Qualité globale</p>
        <p className="text-4xl font-semibold">{rapport.score_global.toFixed(1)} / 100</p>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {dimensions.map(([cle, dimension]) => (
          <CarteDimension key={cle} cle={cle} dimension={dimension} />
        ))}
      </div>
    </div>
  );
}
