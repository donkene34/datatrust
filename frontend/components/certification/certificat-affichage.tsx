/**
 * components/certification/certificat-affichage.tsx (Milestone #5, tâche #10).
 *
 * Composant de présentation pur — affiche un `Certificat` (champs on-chain purs, tels que
 * retournés par GET /api/v1/datasets/{id} et GET /api/v1/certifications/{id}), utilisé sur la
 * page /datasets/[id]. Distinct de ResultatCertificationAffichage (components/certification/
 * resultat-certification.tsx, tâche #7), qui affiche en plus hash_transaction/gas/coût — des
 * champs propres à UNE exécution de certification, connus uniquement juste après l'avoir
 * déclenchée (résultat de job), jamais réexposés par GET /datasets/{id} (confiance.obtenir_
 * certificat() lit uniquement getCertificate() on-chain, qui ne stocke pas le hash de
 * transaction — vérifié dans confiance/client_blockchain.py). Une visite fraîche de cette page
 * (n'importe qui, pas seulement la personne qui vient de certifier) ne peut donc pas afficher de
 * lien vers la transaction — limite du contrat de données actuel, pas un oubli d'affichage.
 */

import type { Certificat } from "@/lib/types";

function LigneChamp({ libelle, valeur, mono = false }: { libelle: string; valeur: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-2">
      <span className="shrink-0 text-xs font-medium uppercase tracking-wide text-zinc-500 sm:w-32">
        {libelle}
      </span>
      <span className={`break-all text-sm ${mono ? "font-mono" : ""}`}>{valeur}</span>
    </div>
  );
}

export function CertificatAffichage({ certificat }: { certificat: Certificat }) {
  const date = new Date(certificat.timestamp * 1000).toLocaleString("fr-FR", {
    dateStyle: "long",
    timeStyle: "short",
  });

  return (
    <div className="w-full max-w-2xl space-y-4 rounded-lg border border-teal-200 bg-teal-50 p-5 dark:border-teal-900 dark:bg-teal-950">
      <div className="text-center">
        <p className="text-sm font-medium text-teal-700 dark:text-teal-300">Certificat blockchain</p>
        <p className="text-3xl font-semibold">{certificat.quality_score.toFixed(1)} / 100</p>
      </div>

      <div className="space-y-2 rounded-md bg-white/60 p-4 dark:bg-black/20">
        <LigneChamp libelle="Version" valeur={String(certificat.version)} />
        <LigneChamp libelle="Certifié le" valeur={date} />
        <LigneChamp libelle="Propriétaire" valeur={certificat.owner} mono />
        <LigneChamp libelle="Certificateur" valeur={certificat.certifier} mono />
        <LigneChamp libelle="Hash dataset" valeur={certificat.dataset_hash} mono />
        <LigneChamp libelle="Hash métadonnées" valeur={certificat.metadata_hash} mono />
        <LigneChamp libelle="CID IPFS" valeur={certificat.ipfs_cid} mono />
      </div>
    </div>
  );
}
