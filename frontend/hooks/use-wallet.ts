"use client";

/**
 * hooks/use-wallet.ts (Milestone #5, tâche #9).
 *
 * Expose { adresse, connecte, connecter, deconnecter } (V2 §9 de la spec) au-dessus de wagmi.
 * Rôle strictement limité à l'identification de l'utilisateur pour pré-remplir owner_address
 * (V3 §2, brief_chatgpt_milestone5.md § "Fait important sur le smart contract") — jamais utilisé
 * pour signer une certification, c'est le wallet plateforme qui signe côté backend.
 *
 * API wagmi vérifiée directement dans le code source installé (wagmi@3.7.6, pas supposée à
 * partir d'une version antérieure de la librairie) : cette version n'expose plus `useAccount`
 * comme hook principal (il ne reste que comme alias dépréciant vers `useConnection`,
 * node_modules/wagmi/dist/esm/exports/index.js) — `useConnection()` est la source de vérité pour
 * { address, isConnected }, `useConnect()`/`useDisconnect()` pour les actions.
 */

import { useConnect, useConnection, useDisconnect } from "wagmi";

export interface UseWalletResultat {
  adresse: string | undefined;
  connecte: boolean;
  connexionEnCours: boolean;
  erreurConnexion: string | null;
  connecter: () => void;
  deconnecter: () => void;
}

export function useWallet(): UseWalletResultat {
  const { address, isConnected } = useConnection();
  const { connect, connectors, isPending, error } = useConnect();
  const { disconnect } = useDisconnect();

  function connecter() {
    // "injected" (lib/blockchain/config.ts) : un seul connecteur configuré pour ce MVP (MetaMask
    // et tout wallet compatible EIP-1193) — pas de sélecteur multi-wallet à construire ici.
    const connecteur = connectors[0];
    if (!connecteur) return;
    connect({ connector: connecteur });
  }

  return {
    adresse: address,
    connecte: isConnected,
    connexionEnCours: isPending,
    erreurConnexion: error ? error.message : null,
    connecter,
    deconnecter: () => disconnect(),
  };
}
