/**
 * components/insights/rapport-insights.tsx (Milestone #5, tâche #6).
 *
 * Composant de présentation pur (pas de "use client") — affiche le bloc "insights_ia" d'un
 * RapportInsights déjà résolu (job "rapport_intelligence" terminé). Les deux formes légitimes de
 * insights_ia (lib/types.ts : normal {resume, insights[], recommandations[]} ou dégradé
 * {erreur}) sont gérées ici, pas laissées à la charge du composant appelant — la dégradation
 * gracieuse (ex. quota Groq dépassé, HTTP 429) est un état "termine" côté job, pas un "echec".
 */

import type { BlocInsightsIA, Insight, RapportInsights } from "@/lib/types";

const LIBELLES_IMPORTANCE: Record<Insight["importance"], string> = {
  elevee: "Élevée",
  moyenne: "Moyenne",
  faible: "Faible",
};

const STYLES_IMPORTANCE: Record<Insight["importance"], string> = {
  elevee: "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300",
  moyenne:
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
  faible:
    "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400",
};

function estBlocEnErreur(bloc: BlocInsightsIA): bloc is { erreur: string } {
  return "erreur" in bloc;
}

function CarteInsight({ insight }: { insight: Insight }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium">{insight.titre}</p>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES_IMPORTANCE[insight.importance]}`}
        >
          {LIBELLES_IMPORTANCE[insight.importance]}
        </span>
      </div>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{insight.description}</p>
    </div>
  );
}

export function RapportInsightsAffichage({ rapport }: { rapport: RapportInsights }) {
  const bloc = rapport.insights_ia;

  if (estBlocEnErreur(bloc)) {
    return (
      <div className="w-full max-w-2xl rounded-lg border border-amber-200 bg-amber-50 p-4 text-center text-sm text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
        <p className="font-medium">Analyse IA indisponible</p>
        <p className="mt-1">{bloc.erreur}</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl space-y-6">
      <div>
        <p className="text-sm font-medium text-zinc-500">Résumé</p>
        <p className="mt-1 text-sm">{bloc.resume}</p>
      </div>

      {bloc.insights.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-zinc-500">Insights</p>
          {bloc.insights.map((insight, index) => (
            <CarteInsight key={index} insight={insight} />
          ))}
        </div>
      )}

      {bloc.recommandations.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-zinc-500">Recommandations</p>
          {bloc.recommandations.map((recommandation, index) => (
            <div
              key={index}
              className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
            >
              <p className="font-medium">{recommandation.titre}</p>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {recommandation.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
