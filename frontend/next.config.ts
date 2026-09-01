import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `next dev` régénère sinon AGENTS.md/CLAUDE.md à chaque lancement — du bruit générique
  // sans rapport avec ce projet (documents/instructions de gouvernance déjà dans docs/).
  agentRules: false,
};

export default nextConfig;
