"use client";

/**
 * components/home/recherche-dataset.tsx (Milestone #5, tâche #11).
 *
 * Saisie d'un dataset_id → navigation vers /datasets/[id]. Seul point d'entrée vers la page de
 * détail pour ce Milestone (pas de liste/découverte des datasets certifiés — Phase 5,
 * Marketplace, complémentaire, hors périmètre ici) : sans ce composant, /datasets/[id] ne serait
 * atteignable que depuis le lien affiché juste après une certification sur /depot, dans le même
 * navigateur — ce qui contredirait la promesse "Data Trust" (page consultable par n'importe qui,
 * pas seulement celui qui vient de certifier).
 */

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

export function RechercheDataset() {
  const router = useRouter();
  const [identifiant, setIdentifiant] = useState("");

  function gererRecherche(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    const valeur = identifiant.trim();
    if (!valeur) return;
    router.push(`/datasets/${valeur}`);
  }

  return (
    <form onSubmit={gererRecherche} className="flex w-full gap-2">
      <input
        type="text"
        inputMode="numeric"
        value={identifiant}
        onChange={(evenement) => setIdentifiant(evenement.target.value)}
        placeholder="Identifiant du dataset (ex. 17)"
        className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
      />
      <button
        type="submit"
        disabled={!identifiant.trim()}
        className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-900"
      >
        Voir
      </button>
    </form>
  );
}
