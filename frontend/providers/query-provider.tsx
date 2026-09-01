"use client";

/**
 * providers/query-provider.tsx (Milestone #5, tâche #2).
 *
 * QueryClient créé via useState (pas un singleton au niveau module) : sous
 * l'App Router, un module partagé entre requêtes SSR risquerait de faire
 * fuiter le cache d'un visiteur vers un autre — un client par montage du
 * provider évite ce piège, pattern recommandé par TanStack Query pour Next.js.
 */

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
