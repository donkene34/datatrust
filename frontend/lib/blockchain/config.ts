/**
 * lib/blockchain/config.ts — configuration wagmi (Milestone #5, tâche #2).
 *
 * Réservé à la connexion du wallet et à la préparation de la Phase 5
 * (transactions utilisateur futures) — jamais utilisé pour lire un
 * certificat ni pour signer une certification (voir V3 §2 de la spec :
 * c'est le wallet plateforme, côté backend, qui signe chaque certification,
 * pas le wallet connecté ici).
 *
 * connector "injected" plutôt qu'un connecteur WalletConnect dédié : couvre
 * MetaMask (et tout wallet compatible EIP-1193 injecté dans window.ethereum)
 * sans nécessiter de clé d'API tierce pour ce MVP.
 */

import { http, createConfig } from "wagmi";
import { sepolia } from "wagmi/chains";
import { injected } from "wagmi/connectors";

export const wagmiConfig = createConfig({
  chains: [sepolia],
  connectors: [injected()],
  transports: {
    [sepolia.id]: http(),
  },
});

declare module "wagmi" {
  interface Register {
    config: typeof wagmiConfig;
  }
}
