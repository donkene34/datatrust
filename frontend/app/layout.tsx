import type { Metadata } from "next";
import "./globals.css";

import { Entete } from "@/components/layout/entete";
import { QueryProvider } from "@/providers/query-provider";
import { WalletProvider } from "@/providers/wallet-provider";

// Pas de next/font/google ici (délibéré) : ça téléchargerait les polices Geist depuis
// fonts.googleapis.com à CHAQUE build — une dépendance réseau externe évitable pour un
// projet de fin de formation qui doit pouvoir builder de façon fiable (démo, soutenance,
// environnement sans accès sortant). La pile système de Tailwind (font-sans) suffit ici.

export const metadata: Metadata = {
  title: "Data Trust & Insights",
  description:
    "Plateforme décentralisée de certification, d'évaluation et d'exploration intelligente des datasets.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">
        <QueryProvider>
          <WalletProvider>
            <Entete />
            {children}
          </WalletProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
