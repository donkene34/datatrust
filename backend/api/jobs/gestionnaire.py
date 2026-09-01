"""
gestionnaire.py — JobManager (Milestone #4, Phase 4a : API Backend).

Couche unique de création/lecture/mise à jour des jobs, persistés en SQLite
(ADR-3 : jamais en mémoire — un job en cours, notamment une certification
avec transaction déjà envoyée, ne doit pas perdre son suivi si le serveur
FastAPI redémarre). N'appelle que des fonctions déjà exposées par les
modules métier (ADR-7) — aucune logique métier propre, hormis l'idempotence
de la certification (ADR-5) et la réconciliation au démarrage (ADR-10), qui
sont explicitement le rôle de ce composant selon la spécification.

Une connexion SQLite est ouverte et refermée à chaque opération plutôt que
gardée ouverte sur la durée de vie du JobManager : sqlite3 n'est pas
thread-safe par défaut entre threads différents, et les tâches FastAPI
BackgroundTasks (utilisées par les futures routes, ADR-1/ADR-2) peuvent
s'exécuter hors du thread principal. Ouvrir une connexion courte par appel
évite ce piège sans complexité supplémentaire — un fichier SQLite local
unique n'a pas besoin d'un pool de connexions pour ce MVP.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from confiance.client_blockchain import obtenir_certificat, obtenir_recu_transaction

from .modeles import (
    ErreurJob,
    Job,
    JobPublic,
    StatutJob,
    TypeJob,
    initialiser_schema,
    job_vers_ligne,
    ligne_vers_job,
    nouveau_job,
)

# Champs qu'un appelant peut modifier via mettre_a_jour_job() — tout le modèle sauf
# job_id (identité immuable) et cree_le (date de création, jamais réécrite après coup).
_CHAMPS_MODIFIABLES = set(Job.model_fields.keys()) - {"job_id", "cree_le"}


class JobManager:
    def __init__(self, chemin_bdd: str):
        self.chemin_bdd = chemin_bdd
        with self._connexion() as connexion:
            initialiser_schema(connexion)

    @contextmanager
    def _connexion(self):
        connexion = sqlite3.connect(self.chemin_bdd)
        connexion.row_factory = sqlite3.Row
        try:
            yield connexion
            connexion.commit()
        finally:
            connexion.close()

    # --- CRUD de base ---

    def creer_job(self, type_job: TypeJob, **champs_internes) -> Job:
        """
        Crée et persiste un nouveau job (statut "en_attente"). champs_internes
        permet de renseigner dès la création chemin_fichier_temp/dataset_hash
        si déjà connus (ADR-6 : le fichier est sauvegardé sur disque de façon
        synchrone avant que le job_id soit renvoyé au client).
        """
        job = nouveau_job(type_job, **champs_internes)
        with self._connexion() as connexion:
            ligne = job_vers_ligne(job)
            connexion.execute(
                """
                INSERT INTO jobs (job_id, type, statut, dataset_hash, transaction_hash,
                                   dataset_id_onchain, cree_le, mis_a_jour_le, donnees_json)
                VALUES (:job_id, :type, :statut, :dataset_hash, :transaction_hash,
                        :dataset_id_onchain, :cree_le, :mis_a_jour_le, :donnees_json)
                """,
                ligne,
            )
        return job

    def lire_job(self, job_id: str) -> Optional[Job]:
        """Lecture interne complète (avec champs internes) — pour les exécutants et le JobManager lui-même."""
        with self._connexion() as connexion:
            ligne = connexion.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return ligne_vers_job(ligne) if ligne else None

    def lire_job_public(self, job_id: str) -> Optional[JobPublic]:
        """Vue exposée par GET /api/v1/jobs/{job_id} — champs internes exclus."""
        job = self.lire_job(job_id)
        return JobPublic.depuis_job(job) if job else None

    def mettre_a_jour_job(self, job_id: str, **champs) -> Job:
        """
        Met à jour un ou plusieurs champs d'un job existant et rafraîchit
        mis_a_jour_le. Lève ValueError si le job n'existe pas ou si un nom
        de champ inconnu est passé (protection contre une faute de frappe
        silencieuse — le job ne serait alors ni mis à jour ni signalé).
        """
        inconnus = set(champs) - _CHAMPS_MODIFIABLES
        if inconnus:
            raise ValueError(f"Champ(s) inconnu(s) pour mettre_a_jour_job : {sorted(inconnus)}")

        job = self.lire_job(job_id)
        if job is None:
            raise ValueError(f"Job introuvable : {job_id}")

        for champ, valeur in champs.items():
            setattr(job, champ, valeur)
        job.mis_a_jour_le = datetime.now(timezone.utc)

        with self._connexion() as connexion:
            ligne = job_vers_ligne(job)
            connexion.execute(
                """
                UPDATE jobs SET type=:type, statut=:statut, dataset_hash=:dataset_hash,
                    transaction_hash=:transaction_hash, dataset_id_onchain=:dataset_id_onchain,
                    cree_le=:cree_le, mis_a_jour_le=:mis_a_jour_le, donnees_json=:donnees_json
                WHERE job_id=:job_id
                """,
                ligne,
            )
        return job

    # --- Idempotence de la certification (ADR-5) ---

    def verifier_idempotence_certification(self, dataset_hash: str):
        """
        Implémente les 3 cas de l'idempotence de la certification (ADR-5),
        en examinant tous les jobs de type "certification" déjà enregistrés
        pour ce dataset_hash :

        - ("termine", job) — un certificat déjà terminé existe pour ce hash
          → l'appelant doit retourner son résultat directement, sans créer
          de nouveau job.
        - ("en_cours", job) — un job en_attente/en_cours existe déjà pour ce
          hash → l'appelant doit retourner ce job existant, sans déclencher
          de nouvelle transaction.
        - ("nouvelle_tentative", None) — premier essai pour ce hash, ou tous
          les jobs précédents se sont terminés en échec (echec ou
          echec_recuperable, qui compte comme un echec pour l'idempotence,
          voir ADR-10 point 4) → l'appelant peut créer un nouveau job.

        Un job "termine" prime toujours sur les autres s'il en existe un,
        même si des tentatives ratées existent aussi pour ce hash.
        """
        with self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT * FROM jobs WHERE dataset_hash = ? AND type = ? ORDER BY cree_le DESC",
                (dataset_hash, TypeJob.CERTIFICATION.value),
            ).fetchall()
        jobs = [ligne_vers_job(ligne) for ligne in lignes]

        for job in jobs:
            if job.statut == StatutJob.TERMINE:
                return "termine", job
        for job in jobs:
            if job.statut in (StatutJob.EN_ATTENTE, StatutJob.EN_COURS):
                return "en_cours", job
        return "nouvelle_tentative", None

    # --- Relation dataset_id ↔ jobs qualité/insights (Milestone #4.1) ---

    def resoudre_jobs_lies(self, dataset_hash: str) -> tuple:
        """
        Retrouve, pour un dataset_hash donné, le job qualité et le job insights
        "termine" les plus récents partageant ce hash — à appeler une seule fois,
        au moment où le job de certification correspondant passe "termine"
        (voir routes/certifications.py), pour figer durablement l'association
        plutôt que de la recalculer à chaque lecture de GET /api/v1/datasets/{id}.

        Retourne (job_qualite_id, job_insights_id), chacun pouvant être None si
        aucun job de ce type n'a été trouvé pour ce hash (ex. certification faite
        sans étape qualité préalable — cas légitime, pas une erreur).
        """

        def _plus_recent_termine(type_job: TypeJob) -> Optional[str]:
            with self._connexion() as connexion:
                ligne = connexion.execute(
                    """
                    SELECT job_id FROM jobs
                    WHERE dataset_hash = ? AND type = ? AND statut = ?
                    ORDER BY cree_le DESC LIMIT 1
                    """,
                    (dataset_hash, type_job.value, StatutJob.TERMINE.value),
                ).fetchone()
            return ligne["job_id"] if ligne else None

        return (
            _plus_recent_termine(TypeJob.RAPPORT_QUALITE),
            _plus_recent_termine(TypeJob.RAPPORT_INTELLIGENCE),
        )

    def trouver_job_certification_par_dataset_id(self, dataset_id: int) -> Optional[Job]:
        """
        Retrouve le job de certification associé à un dataset_id on-chain, via la
        colonne dénormalisée indexée dataset_id_onchain (renseignée par
        resoudre_jobs_lies() + mettre_a_jour_job() au moment où la certification
        aboutit). Retourne None si aucun job de certification n'a cette valeur —
        peut arriver pour un dataset certifié avant l'introduction de cette
        fonctionnalité (Milestone #4.1), ou par un autre moyen que cette API.
        """
        with self._connexion() as connexion:
            ligne = connexion.execute(
                "SELECT * FROM jobs WHERE dataset_id_onchain = ? AND type = ? LIMIT 1",
                (dataset_id, TypeJob.CERTIFICATION.value),
            ).fetchone()
        return ligne_vers_job(ligne) if ligne else None

    # --- Réconciliation au démarrage (ADR-10) ---

    def reconcilier_au_demarrage(self) -> list:
        """
        À appeler une fois, au démarrage de FastAPI (ADR-10) : tout job
        trouvé "en_cours" est soit réconcilié vers "termine" (si sa
        transaction blockchain a en fait été confirmée avec succès entre
        le crash et le redémarrage), soit marqué "echec_recuperable".

        Retourne la liste des jobs traités, sous la forme
        [{"job_id": ..., "issue": "termine" | "echec" | "echec_recuperable"}, ...]
        — utile pour journaliser ce qui s'est passé au démarrage et pour les
        tests.

        Point ouvert, signalé explicitement plutôt que tranché seul : le
        texte de l'ADR-10 ne décrit que deux issues pour un job de
        certification avec transaction_hash déjà connu — "confirmée avec
        succès" (→ termine) et "introuvable/en attente" (→ echec_recuperable).
        obtenir_recu_transaction() (ADR-11) peut aussi renvoyer un troisième
        état, "echouee" (transaction minée mais revert on-chain — un fait
        établi, contrairement à "introuvable" qui reste incertain). Ce cas
        est ici traité comme "echec" (définitif, pas "echec_recuperable" :
        DILANE a précisé que echec_recuperable signifie "pourrait encore se
        confirmer plus tard", ce qui n'est justement plus possible pour une
        transaction dont on sait qu'elle a revert) — à confirmer
        explicitement.
        """
        with self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT * FROM jobs WHERE statut = ?", (StatutJob.EN_COURS.value,)
            ).fetchall()
        jobs_en_cours = [ligne_vers_job(ligne) for ligne in lignes]

        resume = []
        for job in jobs_en_cours:
            if job.type == TypeJob.CERTIFICATION and job.transaction_hash:
                resume.append(self._reconcilier_job_certification(job))
            else:
                # Crash avant l'étape blockchain (ou job qualité/insights) : pas de transaction à
                # vérifier, on ne peut rien reconstituer — echec_recuperable (ADR-10 point 3).
                self.mettre_a_jour_job(job.job_id, statut=StatutJob.ECHEC_RECUPERABLE)
                resume.append({"job_id": job.job_id, "issue": "echec_recuperable"})
        return resume

    def _reconcilier_job_certification(self, job: Job) -> dict:
        recu = obtenir_recu_transaction(job.transaction_hash)
        statut_recu = recu.get("statut")

        if statut_recu == "confirmee":
            resultat_complet = obtenir_certificat(recu["dataset_id"])
            self.mettre_a_jour_job(job.job_id, statut=StatutJob.TERMINE, resultat=resultat_complet)
            return {"job_id": job.job_id, "issue": "termine"}

        if statut_recu == "echouee":
            self.mettre_a_jour_job(
                job.job_id,
                statut=StatutJob.ECHEC,
                erreur=ErreurJob(
                    code="transaction_blockchain_echec",
                    message="Transaction minée mais échouée on-chain (constaté à la réconciliation au démarrage).",
                ),
            )
            return {"job_id": job.job_id, "issue": "echec"}

        # statut_recu == "introuvable" (transaction encore en attente de minage), ou {"erreur": ...}
        # (RPC/config injoignable au moment de la réconciliation) : dans les deux cas, l'état réel
        # n'est pas connu avec certitude — echec_recuperable plutôt qu'une conclusion hâtive.
        self.mettre_a_jour_job(job.job_id, statut=StatutJob.ECHEC_RECUPERABLE)
        return {"job_id": job.job_id, "issue": "echec_recuperable"}

    # --- Nettoyage des fichiers temporaires (ADR-9) ---

    def nettoyer_fichiers_expires(self, ttl_heures: float) -> list:
        """
        Supprime du disque les fichiers temporaires (jamais les lignes de la
        table jobs elles-mêmes) dont TOUS les jobs qui les référencent sont
        dans un état terminal (termine/echec/echec_recuperable) depuis plus
        de ttl_heures — l'ancienneté est mesurée depuis le job le plus
        récemment mis à jour parmi ceux qui partagent ce chemin.

        Un même chemin_fichier_temp peut être référencé par plusieurs jobs
        (ex. un job qualité et le job insights qui le réutilise, ADR-12) :
        un fichier encore référencé par au moins un job en_attente/en_cours
        n'est **jamais** supprimé, quel que soit son âge (critère #14) —
        c'est vérifié ici en regroupant tous les jobs par chemin avant de
        décider, plutôt qu'en examinant chaque job isolément.

        Limite assumée pour ce Milestone, dans le même esprit que la
        réconciliation (ADR-10, point 5) : ce nettoyage doit être déclenché
        explicitement (ici, une fois au démarrage de FastAPI, voir main.py)
        — aucune tâche planifiée périodique n'est mise en place pour ce MVP.

        Retourne la liste des chemins effectivement supprimés (logs/tests).
        """
        with self._connexion() as connexion:
            lignes = connexion.execute("SELECT * FROM jobs").fetchall()
        tous_les_jobs = [ligne_vers_job(ligne) for ligne in lignes]

        jobs_par_chemin = {}
        for job in tous_les_jobs:
            if job.chemin_fichier_temp:
                jobs_par_chemin.setdefault(job.chemin_fichier_temp, []).append(job)

        maintenant = datetime.now(timezone.utc)
        seuil = timedelta(hours=ttl_heures)
        chemins_supprimes = []

        for chemin, jobs_lies in jobs_par_chemin.items():
            un_job_actif = any(job.statut in (StatutJob.EN_ATTENTE, StatutJob.EN_COURS) for job in jobs_lies)
            if un_job_actif:
                continue  # critère #14 : jamais nettoyé tant qu'un job actif référence ce fichier

            job_le_plus_recent = max(jobs_lies, key=lambda job: job.mis_a_jour_le)
            if maintenant - job_le_plus_recent.mis_a_jour_le <= seuil:
                continue  # pas encore expiré

            if os.path.exists(chemin):
                try:
                    os.remove(chemin)
                    chemins_supprimes.append(chemin)
                except OSError:
                    # fichier déjà absent entre-temps ou verrouillé — pas fatal, retenté au
                    # prochain passage plutôt que de faire planter le nettoyage entier
                    pass

        return chemins_supprimes
