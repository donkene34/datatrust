import Link from "next/link";

import { RechercheDataset } from "@/components/home/recherche-dataset";

/**
 * Page d'accueil réelle (Milestone #5, tâche #11) : présentation courte de la plateforme, CTA
 * vers /depot, et recherche d'un dataset déjà certifié par identifiant (voir
 * components/home/recherche-dataset.tsx pour la justification de ce second point d'entrée).
 */
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-10 p-8 text-center">
      <div className="flex max-w-lg flex-col items-center gap-4">
        <h1 className="text-3xl font-semibold">Data Trust &amp; Insights</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Certifiez la provenance et la qualité de vos datasets, obtenez une analyse IA de leur
          contenu, et ancrez la preuve sur la blockchain Sepolia — vérifiable par n’importe qui, à
          tout moment.
        </p>
        <Link
          href="/depot"
          className="rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc]"
        >
          Déposer un dataset
        </Link>
      </div>

      <div className="flex w-full max-w-sm flex-col items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Consulter un dataset déjà certifié
        </p>
        <RechercheDataset />
      </div>
    </main>
  );
}
