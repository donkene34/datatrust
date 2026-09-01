"use client";

/**
 * components/wallet/badge-wallet.tsx (Milestone #5, tâche #9).
 *
 * Badge d'adresse connectée + bouton de connexion/déconnexion (V2 §9 de la spec). Affiché dans
 * app/layout.tsx, donc visible sur toutes les pages — la navigation complète (tâche #11) pourra
 * le reprendre tel quel dans un header plus élaboré, sans le modifier.
 */

import { useWallet } from "@/hooks/use-wallet";

function tronquerAdresse(adresse: string): string {
  return `${adresse.slice(0, 6)}…${adresse.slice(-4)}`;
}

export function BadgeWallet() {
  const { adresse, connecte, connexionEnCours, erreurConnexion, connecter, deconnecter } =
    useWallet();

  if (connecte && adresse) {
    return (
      <div className="flex items-center gap-2">
        <span
          title={adresse}
          className="rounded-full border border-teal-600 px-3 py-1 font-mono text-xs text-teal-700 dark:border-teal-500 dark:text-teal-300"
        >
          {tronquerAdresse(adresse)}
        </span>
        <button
          type="button"
          onClick={deconnecter}
          className="text-xs text-zinc-500 underline underline-offset-2 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          Déconnecter
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={connecter}
        disabled={connexionEnCours}
        className="rounded-full border border-zinc-300 px-3 py-1 text-xs font-medium transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-900"
      >
        {connexionEnCours ? "Connexion…" : "Connecter un wallet"}
      </button>
      {erreurConnexion && <p className="text-xs text-red-600">{erreurConnexion}</p>}
    </div>
  );
}
