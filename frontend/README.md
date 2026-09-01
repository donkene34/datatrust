# Data Trust & Insights — Interface

Frontend Next.js (Milestone #5, Phase 4b) de la plateforme de certification, d'évaluation et
d'exploration intelligente de datasets. Consomme l'API FastAPI du Milestone #4
(`../backend/`) — voir `docs/milestone_4_api.md` et `docs/milestone_5_v3_interface.md` à la
racine du dépôt pour la spécification complète.

## Démarrage

```bash
npm install
cp .env.local.example .env.local   # ajuster NEXT_PUBLIC_CONTRACT_ADDRESS si besoin
npm run dev
```

Ouvrir [http://localhost:3000](http://localhost:3000). L'API backend doit tourner en parallèle
sur `http://localhost:8000` (voir `backend/README` / `docs/procedure_verification_phase4a.md`).

## Stack

Next.js (App Router) + TypeScript + Tailwind CSS + TanStack Query (polling des jobs
asynchrones) + wagmi/viem (connexion wallet uniquement — voir `lib/blockchain/config.ts`).

## Structure

```
app/            routes (App Router)
components/     composants React, un dossier par domaine (créés au fil des tâches)
lib/api/        clients HTTP vers le backend FastAPI
lib/blockchain/ configuration wagmi
lib/erreurs.ts  mapping code d'erreur backend -> message humain
hooks/          use-job (polling), use-wallet
providers/      QueryClientProvider, WagmiProvider
```
