/**
 * components/certification/resultat-certification.tsx (Milestone #5, tâche #6).
 *
 * Composant de présentation pur (pas de "use client") — affiche un ResultatCertification déjà
 * résolu, que ce soit via un job "certification" terminé ou via la réponse 200 directe de
 * l'idempotence cas (a) (lib/api/certifications.ts). Champs affichés conformes à V2 §7.4 de la
 * spec Milestone #5 : dataset_id, version, hash, CID IPFS, transaction_hash, lien vers la page de
 * détail. Le lien Etherscan Sepolia est un ajout de présentation (lecture seule, cohérent avec
 * l'ADR-8 du Milestone #3 — vérification manuelle via Etherscan) et n'engage aucune décision
 * d'architecture.
 */

import Link from "next/link";

import type { ResultatCertification } from "@/lib/types";

function LigneChamp({ libelle, valeur, mono = false }: { libelle: string; valeur: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-2">
      <span className="shrink-0 text-xs font-medium uppercase tracking-wide text-zinc-500 sm:w-32">
        {libelle}
      </span>
      <span className={`break-all text-sm ${mono ? "font-mono" : ""}`}>{valeur}</span>
    </div>
  );
}

export function ResultatCertificationAffichage({ resultat }: { resultat: ResultatCertification }) {
  return (
    <div className="w-full max-w-2xl space-y-4 rounded-lg border border-teal-200 bg-teal-50 p-5 dark:border-teal-900 dark:bg-teal-950">
      <div className="text-center">
        <p className="text-sm font-medium text-teal-700 dark:text-teal-300">Dataset certifié</p>
        <p className="text-3xl font-semibold">#{resultat.dataset_id}</p>
      </div>

      <div className="space-y-2 rounded-md bg-white/60 p-4 dark:bg-black/20">
        <LigneChamp libelle="Version" valeur={String(resultat.version)} />
        <LigneChamp libelle="Score qualité" valeur={`${resultat.quality_score.toFixed(1)} / 100`} />
        <LigneChamp libelle="Propriétaire" valeur={resultat.owner} mono />
        <LigneChamp libelle="Hash dataset" valeur={resultat.dataset_hash} mono />
        <LigneChamp libelle="CID IPFS" valeur={resultat.ipfs_cid} mono />
        <LigneChamp libelle="Transaction" valeur={resultat.hash_transaction} mono />
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4 text-sm">
        <Link
          href={`/datasets/${resultat.dataset_id}`}
          className="rounded-full bg-foreground px-4 py-2 font-medium text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc]"
        >
          Voir la page du dataset
        </Link>
        <a
          href={`https://sepolia.etherscan.io/tx/${resultat.hash_transaction}`}
          target="_blank"
          rel="noreferrer"
          className="text-zinc-500 underline underline-offset-2 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          Voir la transaction sur Etherscan
        </a>
      </div>
    </div>
  );
}
