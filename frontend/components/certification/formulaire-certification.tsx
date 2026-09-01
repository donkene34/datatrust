"use client";

/**
 * components/certification/formulaire-certification.tsx (Milestone #5, tâche #7).
 *
 * Deux étapes explicites (V3 §2 de la spec) : "formulaire" (saisie de owner_address, éditable —
 * le pré-remplissage depuis le wallet connecté arrive en tâche #9, pas construit ici) puis
 * "confirmation" (avertissement + double bouton Annuler/Confirmer). L'appel réel à
 * lib/api/certifications.ts n'est déclenché que par onConfirmer, jamais par onContinuer — c'est
 * la garantie demandée par DILANE que l'action irréversible (IPFS + transaction Sepolia) ne parte
 * jamais d'un simple clic sur "Certifier".
 *
 * "use client" : formulaire contrôlé (state géré par le parent, ce composant reste sans state
 * propre au-delà de l'affichage conditionnel des deux étapes).
 */

export type EtapeCertification = "formulaire" | "confirmation";

interface FormulaireCertificationProps {
  etape: EtapeCertification;
  ownerAddress: string;
  onChangeOwnerAddress: (valeur: string) => void;
  onAnnuler: () => void;
  onContinuer: () => void;
  onConfirmer: () => void;
  enCours: boolean;
  erreur: string | null;
}

export function FormulaireCertification({
  etape,
  ownerAddress,
  onChangeOwnerAddress,
  onAnnuler,
  onContinuer,
  onConfirmer,
  enCours,
  erreur,
}: FormulaireCertificationProps) {
  if (etape === "confirmation") {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-lg border border-amber-200 bg-amber-50 p-5 text-center dark:border-amber-900 dark:bg-amber-950">
        <p className="font-semibold text-amber-800 dark:text-amber-200">Certifier ce dataset ?</p>
        <p className="text-sm text-amber-700 dark:text-amber-300">
          Cette action stocke le fichier sur IPFS et enregistre son empreinte sur la blockchain
          Sepolia. Elle est irréversible.
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onAnnuler}
            disabled={enCours}
            className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={onConfirmer}
            disabled={enCours}
            className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-[#ccc]"
          >
            {enCours ? "Certification en cours…" : "Confirmer la certification"}
          </button>
        </div>
        {erreur && <p className="text-sm text-red-600">{erreur}</p>}
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-3 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
      <p className="font-medium">Certifier ce dataset</p>
      <label className="flex w-full flex-col gap-1 text-left text-sm">
        <span className="text-zinc-600 dark:text-zinc-400">Adresse propriétaire (owner_address)</span>
        <input
          type="text"
          value={ownerAddress}
          onChange={(evenement) => onChangeOwnerAddress(evenement.target.value)}
          placeholder="0x..."
          className="rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={onAnnuler}
          className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Annuler
        </button>
        <button
          type="button"
          onClick={onContinuer}
          disabled={!ownerAddress.trim()}
          className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-[#ccc]"
        >
          Continuer
        </button>
      </div>
    </div>
  );
}
