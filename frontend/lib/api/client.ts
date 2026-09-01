/**
 * lib/api/client.ts — fetch wrapper commun à tout lib/api/*.ts (Milestone #5, tâche #3).
 *
 * Deux fonctions génériques (JSON et multipart) plutôt qu'un fetch dupliqué dans chaque fichier
 * lib/api/*.ts (qualite.ts, insights.ts, certifications.ts, jobs.ts, datasets.ts — tâches #4 à #7
 * et #10). Chacune renvoie { statut, corps } — le code HTTP est nécessaire au moins une fois
 * (POST /certifications retourne 200 OU 202 selon l'idempotence, voir V3 §5 de la spec) plutôt
 * que jeté après coup.
 */

import type { ErreurApiPayload } from "@/lib/types";

/** Erreur levée pour toute réponse HTTP 4xx/5xx dont le corps suit le format uniforme
 * {"erreur": {"code", "message"}} — code et statut exploitables séparément par
 * lib/erreurs.ts (tâche #8) pour l'affichage, sans reparser le message. */
export class ErreurApi extends Error {
  readonly code: string;
  readonly statut: number;

  constructor(code: string, message: string, statut: number) {
    super(message);
    this.name = "ErreurApi";
    this.code = code;
    this.statut = statut;
  }
}

const URL_BASE_API = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;

function estPayloadErreurUniforme(corps: unknown): corps is ErreurApiPayload {
  return (
    typeof corps === "object" &&
    corps !== null &&
    "erreur" in corps &&
    typeof (corps as { erreur?: unknown }).erreur === "object" &&
    (corps as { erreur?: unknown }).erreur !== null
  );
}

async function leverErreurApi(reponse: Response): Promise<never> {
  let corps: unknown = null;
  try {
    corps = await reponse.json();
  } catch {
    // Réponse non-JSON (ex. proxy, erreur réseau intermédiaire) — pas le format uniforme attendu,
    // on retombe sur le message générique ci-dessous plutôt que de lever une exception de parsing.
  }
  if (estPayloadErreurUniforme(corps)) {
    throw new ErreurApi(corps.erreur.code, corps.erreur.message, reponse.status);
  }
  throw new ErreurApi(
    "erreur_inconnue",
    `Réponse HTTP ${reponse.status} sans corps d'erreur exploitable.`,
    reponse.status,
  );
}

export interface ReponseApi<T> {
  statut: number;
  corps: T;
}

/** Requête JSON (GET, ou POST avec un corps JSON — ex. POST /insights/rapports {"job_id"}). */
export async function requeteJson<T>(chemin: string, options: RequestInit = {}): Promise<ReponseApi<T>> {
  const reponse = await fetch(`${URL_BASE_API}${chemin}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  if (!reponse.ok) {
    await leverErreurApi(reponse);
  }
  const corps = (await reponse.json()) as T;
  return { statut: reponse.status, corps };
}

/** Requête multipart/form-data (upload de fichier — qualité, certification, vérification).
 * Pas de Content-Type manuel : le navigateur pose lui-même le bon boundary multipart, un
 * Content-Type fixé à la main casserait l'envoi (boundary manquant). */
export async function requeteMultipart<T>(
  chemin: string,
  corpsFormulaire: FormData,
  options: RequestInit = {},
): Promise<ReponseApi<T>> {
  const reponse = await fetch(`${URL_BASE_API}${chemin}`, {
    ...options,
    method: options.method ?? "POST",
    body: corpsFormulaire,
  });
  if (!reponse.ok) {
    await leverErreurApi(reponse);
  }
  const corps = (await reponse.json()) as T;
  return { statut: reponse.status, corps };
}
