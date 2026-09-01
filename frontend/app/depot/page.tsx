import { Suspense } from "react";

import { DepotContenu } from "@/components/depot/depot-contenu";

/**
 * Server component délibérément — DepotContenu ("use client") utilise useJob(), qui appelle
 * useSearchParams(). Next.js exige un <Suspense> autour de tout composant qui en dépend (vérifié
 * en tâche #4 via un build réel, pas supposé) : le séparer ainsi plutôt que de mettre "use client"
 * directement sur cette page satisfait cette contrainte.
 */
export default function DepotPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center">
      <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Chargement…</p>}>
        <DepotContenu />
      </Suspense>
    </main>
  );
}
