"use client";

/**
 * components/certification/verification-integrite.tsx (Milestone #5, tâche #10).
 *
 * Section "vérification d'intégrité" de la page /datasets/[id] (V2 §8 de la spec) : upload d'un
 * fichier, comparé synchroniquement (POST /certifications/{id}/verifier, aucun job — ADR-4 du
 * Milestone #4) au certificat déjà on-chain pour ce dataset_id.
 */

import { useState } from "react";

import { verifierIntegrite } from "@/lib/api/datasets";
import { traduireErreurInconnue } from "@/lib/erreurs";
import type { ResultatVerification } from "@/lib/types";

export function VerificationIntegrite({ datasetId }: { datasetId: number }) {
  const [fichier, setFichier] = useState<File | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [resultat, setResultat] = useState<ResultatVerification | null>(null);

  async function gererVerification() {
    if (!fichier) return;
    setEnCours(true);
    setErreur(null);
    setResultat(null);
    try {
      const reponse = await verifierIntegrite(datasetId, fichier);
      setResultat(reponse);
    } catch (erreurAttrapee) {
      setErreur(traduireErreurInconnue(erreurAttrapee));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-3 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
      <p className="font-medium">Vérifier l’intégrité d’un fichier</p>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Déposez un fichier pour vérifier qu’il correspond exactement à la version certifiée de ce
        dataset.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="file"
          onChange={(evenement) => {
            setFichier(evenement.target.files?.[0] ?? null);
            setResultat(null);
            setErreur(null);
          }}
          className="text-sm"
        />
        <button
          type="button"
          onClick={gererVerification}
          disabled={!fichier || enCours}
          className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-[#ccc]"
        >
          {enCours ? "Vérification…" : "Vérifier"}
        </button>
      </div>

      {erreur && <p className="text-sm text-red-600">{erreur}</p>}

      {resultat &&
        (resultat.identique ? (
          <div className="rounded-md border border-teal-200 bg-teal-50 p-3 text-sm text-teal-700 dark:border-teal-900 dark:bg-teal-950 dark:text-teal-300">
            ✓ Fichier identique au certificat on-chain.
          </div>
        ) : (
          <div className="space-y-1 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            <p>✗ Ce fichier ne correspond pas au certificat on-chain.</p>
            <p className="break-all font-mono text-xs">Hash recalculé : {resultat.hash_recalcule}</p>
            <p className="break-all font-mono text-xs">Hash certifié : {resultat.hash_certifie}</p>
          </div>
        ))}
    </div>
  );
}
