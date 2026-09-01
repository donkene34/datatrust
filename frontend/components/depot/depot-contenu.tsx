"use client";

/**
 * components/depot/depot-contenu.tsx (Milestone #5, tâches #5, #6, #7, #8 et #9).
 *
 * Tâche #8 : tous les messages d'erreur affichés (échec de requête HTTP comme échec de job)
 * passent par lib/erreurs.ts (traduireErreurInconnue / traduireErreurJob) plutôt que par des
 * chaînes ad hoc dispersées dans ce composant — un seul mapping code → message pour les 3 étapes.
 *
 * Tâche #9 : ownerAddress est pré-rempli depuis useWallet() (si connecté) au moment où le
 * formulaire de certification s'ouvre, mais seulement si le champ est encore vide — jamais de
 * verrouillage, conformément à l'arbitrage DILANE (V3 §2 : "pré-rempli mais éditable").
 *
 * Étape 1 du flux /depot (V3 §7 de la spec) : upload CSV → qualité déclenchée automatiquement
 * après l'upload → affichage du rapport une fois le job "termine". Une fois le rapport qualité
 * affiché, "Analyser avec l'IA" (tâche #6) et "Certifier" (tâche #7) sont visibles simultanément
 * (V2 §7.2 — pas de séquence imposée entre les deux).
 *
 * "use client" + doit être rendu sous un <Suspense> (voir hooks/use-job.ts) — géré par
 * app/depot/page.tsx, pas ici.
 *
 * resetTout() (tâche #6) remplace l'usage direct de qualite.reinitialiser()/insights.reinitialiser()
 * pour les actions "tout recommencer" : chaque reinitialiser() de hooks/use-job.ts recalcule l'URL
 * à partir du même searchParams (celui du rendu courant) — deux appels séquentiels dans le même
 * gestionnaire d'événement écraseraient l'un l'autre via router.replace() et seul le dernier
 * paramètre retiré survivrait réellement dans l'URL. En vidant la query string d'un seul coup ici,
 * ce risque disparaît. (Le bouton "Réessayer la certification", tâche #7, appelle lui
 * certification.reinitialiser() seul — un seul paramètre à retirer dans ce gestionnaire, donc pas
 * le même risque.)
 *
 * Point à noter (tâche #7) : POST /api/v1/certifications exige le FICHIER lui-même en multipart
 * (routes/certifications.py — jamais un job_id, contrairement à /insights/rapports), donc le
 * `fichier` (state local depuis l'upload initial) doit rester disponible en mémoire jusqu'à la
 * certification. Un rechargement de page après le job qualité mais avant la certification perd cet
 * objet File (les job_id qualité/insights survivent dans l'URL, pas le fichier lui-même) : le
 * bouton "Certifier" se désactive alors avec un message explicite plutôt que d'échouer
 * silencieusement à l'appel. Pas une régression introduite ici — c'est une limite déjà présente
 * dans le contrat backend, désormais rendue visible plutôt que masquée.
 */

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { FormulaireCertification } from "@/components/certification/formulaire-certification";
import type { EtapeCertification } from "@/components/certification/formulaire-certification";
import { ResultatCertificationAffichage } from "@/components/certification/resultat-certification";
import { RapportInsightsAffichage } from "@/components/insights/rapport-insights";
import { RapportQualiteAffichage } from "@/components/qualite/rapport-qualite";
import { useJob } from "@/hooks/use-job";
import { useWallet } from "@/hooks/use-wallet";
import { certifierDataset } from "@/lib/api/certifications";
import { lancerInsights } from "@/lib/api/insights";
import { deposerQualite } from "@/lib/api/qualite";
import { traduireErreurInconnue, traduireErreurJob } from "@/lib/erreurs";
import type { RapportInsights, RapportQualite, ResultatCertification } from "@/lib/types";

export function DepotContenu() {
  const router = useRouter();
  const pathname = usePathname();

  const [fichier, setFichier] = useState<File | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = useState(false);
  const [erreurEnvoi, setErreurEnvoi] = useState<string | null>(null);

  const [lancementInsightsEnCours, setLancementInsightsEnCours] = useState(false);
  const [erreurLancementInsights, setErreurLancementInsights] = useState<string | null>(null);

  const [etapeCertification, setEtapeCertification] = useState<EtapeCertification | null>(null);
  const [ownerAddress, setOwnerAddress] = useState("");
  const [lancementCertificationEnCours, setLancementCertificationEnCours] = useState(false);
  const [erreurLancementCertification, setErreurLancementCertification] = useState<string | null>(null);
  const [resultatDirect, setResultatDirect] = useState<ResultatCertification | null>(null);

  const qualite = useJob("qualite");
  const insights = useJob("insights");
  const certification = useJob("certification");
  const wallet = useWallet();

  function resetTout() {
    router.replace(pathname, { scroll: false });
  }

  function reessayerCertification() {
    setResultatDirect(null);
    setEtapeCertification(null);
    setErreurLancementCertification(null);
    certification.reinitialiser();
  }

  async function gererDepot() {
    if (!fichier) return;
    setEnvoiEnCours(true);
    setErreurEnvoi(null);
    try {
      const job = await deposerQualite(fichier);
      qualite.demarrerJob(job.job_id);
    } catch (erreur) {
      setErreurEnvoi(traduireErreurInconnue(erreur));
    } finally {
      setEnvoiEnCours(false);
    }
  }

  async function gererAnalyseIA() {
    if (!qualite.jobId) return;
    setLancementInsightsEnCours(true);
    setErreurLancementInsights(null);
    try {
      const job = await lancerInsights(qualite.jobId);
      insights.demarrerJob(job.job_id);
    } catch (erreur) {
      setErreurLancementInsights(traduireErreurInconnue(erreur));
    } finally {
      setLancementInsightsEnCours(false);
    }
  }

  async function gererConfirmerCertification() {
    if (!fichier) return;
    setLancementCertificationEnCours(true);
    setErreurLancementCertification(null);
    try {
      const reponse = await certifierDataset(fichier, ownerAddress.trim());
      if (reponse.type === "resultat_direct") {
        // Cas (a) de l'idempotence (ADR-5) : certificat déjà terminé pour ce hash, aucun job.
        setResultatDirect(reponse.resultat);
      } else {
        certification.demarrerJob(reponse.job.job_id);
      }
      setEtapeCertification(null);
    } catch (erreur) {
      setErreurLancementCertification(traduireErreurInconnue(erreur));
    } finally {
      setLancementCertificationEnCours(false);
    }
  }

  // Aucun job qualité en cours ni terminé pour cette page : formulaire de dépôt.
  if (!qualite.jobId) {
    return (
      <div className="flex w-full max-w-md flex-col items-center gap-4 p-8 text-center">
        <h1 className="text-xl font-semibold">Déposer un dataset</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Fichier CSV uniquement. L’analyse qualité démarre automatiquement après l’envoi.
        </p>
        <input
          type="file"
          accept=".csv"
          onChange={(evenement) => setFichier(evenement.target.files?.[0] ?? null)}
          className="text-sm"
        />
        <button
          type="button"
          onClick={gererDepot}
          disabled={!fichier || envoiEnCours}
          className="rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-[#ccc]"
        >
          {envoiEnCours ? "Envoi en cours…" : "Analyser la qualité"}
        </button>
        {erreurEnvoi && <p className="text-sm text-red-600">{erreurEnvoi}</p>}
      </div>
    );
  }

  // Job créé mais pas encore de première réponse, ou en_attente/en_cours : état indéterminé
  // uniquement (V2 §2 de la spec) — jamais de barre de progression chiffrée, puisque l'API ne
  // renseigne jamais "progression" pour ce Milestone.
  if (qualite.chargement || qualite.enCours) {
    return (
      <div className="flex flex-col items-center gap-2 p-8 text-center">
        <p className="text-lg font-medium">Analyse en cours…</p>
        <p className="max-w-sm text-sm text-zinc-500">
          Votre dataset est en cours d’analyse. Cette opération peut prendre quelques instants.
        </p>
      </div>
    );
  }

  if (qualite.echec) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-red-600">{traduireErreurJob(qualite.erreurJob)}</p>
        <button
          type="button"
          onClick={resetTout}
          className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Réessayer avec un autre fichier
        </button>
      </div>
    );
  }

  if (qualite.termine && qualite.job?.resultat) {
    return (
      <div className="flex flex-col items-center gap-6 p-8">
        <RapportQualiteAffichage rapport={qualite.job.resultat as unknown as RapportQualite} />

        {/* Tâche #6 : analyse IA, déclenchée par bouton (flux semi-automatique, V3 §7). */}
        {!insights.jobId && (
          <div className="flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={gererAnalyseIA}
              disabled={lancementInsightsEnCours}
              className="rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-[#ccc]"
            >
              {lancementInsightsEnCours ? "Lancement…" : "Analyser avec l’IA"}
            </button>
            {erreurLancementInsights && (
              <p className="text-sm text-red-600">{erreurLancementInsights}</p>
            )}
          </div>
        )}

        {insights.jobId && (insights.chargement || insights.enCours) && (
          <div className="flex flex-col items-center gap-2 text-center">
            <p className="text-sm font-medium">Analyse IA en cours…</p>
            <p className="max-w-sm text-xs text-zinc-500">
              Cette opération peut prendre quelques instants.
            </p>
          </div>
        )}

        {insights.jobId && insights.echec && (
          <div className="flex flex-col items-center gap-3 text-center">
            <p className="text-sm text-red-600">{traduireErreurJob(insights.erreurJob)}</p>
            <button
              type="button"
              onClick={gererAnalyseIA}
              disabled={lancementInsightsEnCours}
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              Réessayer l’analyse IA
            </button>
          </div>
        )}

        {insights.termine && insights.job?.resultat && (
          <RapportInsightsAffichage rapport={insights.job.resultat as unknown as RapportInsights} />
        )}

        {/* Tâche #7 : certification, avec étape de confirmation explicite (V3 §2). */}
        {(resultatDirect || (certification.termine && certification.job?.resultat)) && (
          <ResultatCertificationAffichage
            resultat={
              resultatDirect ??
              (certification.job!.resultat as unknown as ResultatCertification)
            }
          />
        )}

        {!resultatDirect && !certification.jobId && (
          <>
            {etapeCertification === null ? (
              fichier ? (
                <button
                  type="button"
                  onClick={() => {
                    // Pré-rempli mais éditable (arbitrage DILANE, V3) : seulement si le champ est
                    // encore vide — un utilisateur qui a déjà modifié owner_address ne doit jamais
                    // se le faire écraser par une reconnexion/relecture du wallet.
                    if (!ownerAddress && wallet.adresse) setOwnerAddress(wallet.adresse);
                    setEtapeCertification("formulaire");
                  }}
                  className="rounded-full border border-teal-600 px-5 py-2.5 text-sm font-medium text-teal-700 transition-colors hover:bg-teal-50 dark:border-teal-500 dark:text-teal-300 dark:hover:bg-teal-950"
                >
                  Certifier
                </button>
              ) : (
                <p className="max-w-sm text-center text-xs text-zinc-500">
                  Fichier non disponible pour la certification (probablement suite à un
                  rechargement de la page) — déposez-le à nouveau pour pouvoir certifier.
                </p>
              )
            ) : (
              <FormulaireCertification
                etape={etapeCertification}
                ownerAddress={ownerAddress}
                onChangeOwnerAddress={setOwnerAddress}
                onAnnuler={() =>
                  setEtapeCertification(etapeCertification === "confirmation" ? "formulaire" : null)
                }
                onContinuer={() => setEtapeCertification("confirmation")}
                onConfirmer={gererConfirmerCertification}
                enCours={lancementCertificationEnCours}
                erreur={erreurLancementCertification}
              />
            )}
          </>
        )}

        {certification.jobId && (certification.chargement || certification.enCours) && (
          <div className="flex flex-col items-center gap-2 text-center">
            <p className="text-sm font-medium">Certification en cours…</p>
            <p className="max-w-sm text-xs text-zinc-500">
              Enregistrement sur IPFS et sur la blockchain Sepolia — cette opération peut prendre
              quelques instants.
            </p>
          </div>
        )}

        {certification.jobId && certification.echec && (
          <div className="flex flex-col items-center gap-3 text-center">
            <p className="text-sm text-red-600">{traduireErreurJob(certification.erreurJob)}</p>
            <button
              type="button"
              onClick={reessayerCertification}
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              Réessayer la certification
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={resetTout}
          className="text-sm text-zinc-500 underline underline-offset-2 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          Déposer un autre fichier
        </button>
      </div>
    );
  }

  return null;
}
