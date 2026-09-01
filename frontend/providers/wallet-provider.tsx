"use client";

/**
 * providers/wallet-provider.tsx (Milestone #5, tâche #2).
 *
 * Wrapper autour de wagmi (voir lib/blockchain/config.ts). Le hook
 * hooks/use-wallet.ts (tâche #9) consommera ce contexte — ce provider ne
 * fait rien d'autre que le rendre disponible à toute la page.
 */

import { WagmiProvider } from "wagmi";

import { wagmiConfig } from "@/lib/blockchain/config";

export function WalletProvider({ children }: { children: React.ReactNode }) {
  return <WagmiProvider config={wagmiConfig}>{children}</WagmiProvider>;
}
