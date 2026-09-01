/**
 * components/layout/entete.tsx (Milestone #5, tâche #11).
 *
 * Navigation réelle : reprend telle quelle la barre minimale de la tâche #9 (BadgeWallet) et
 * l'étoffe avec le nom de la plateforme (lien vers l'accueil) et le lien vers /depot. Pas de lien
 * vers une liste de datasets certifiés — cette page n'existe pas encore (Phase 5, Marketplace,
 * complémentaire) ; la recherche par identifiant sur la page d'accueil (RechercheDataset) est le
 * seul chemin de navigation vers /datasets/[id] pour ce Milestone.
 *
 * Pas "use client" : aucun état ni hook propre à ce composant — BadgeWallet (lui "use client")
 * peut être rendu tel quel depuis un server component.
 */

import Link from "next/link";

import { BadgeWallet } from "@/components/wallet/badge-wallet";

export function Entete() {
  return (
    <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
      <Link href="/" className="text-sm font-semibold">
        Data Trust &amp; Insights
      </Link>
      <nav className="flex items-center gap-4 text-sm">
        <Link
          href="/depot"
          className="text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          Déposer un dataset
        </Link>
        <BadgeWallet />
      </nav>
    </header>
  );
}
