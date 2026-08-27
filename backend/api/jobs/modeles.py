"""
modeles.py — Schéma du Job (Milestone #4, Phase 4a : API Backend), tel que
défini dans milestone_4_api.md § "Cycle de vie d'un job".

Un job représente une opération asynchrone (rapport qualité, rapport
d'intelligence, ou certification) suivie via `GET /api/v1/jobs/{job_id}` et
persistée en SQLite (ADR-3) — jamais en mémoire, pour survivre à un
redémarrage du serveur FastAPI (voir la réconciliation au démarrage,
ADR-10, implémentée dans gestionnaire.py).

Ce module ne contient aucune logique métier (ADR-7) : uniquement la forme
des données (modèles Pydantic) et le schéma de la table SQLite qui les
stocke, plus les fonctions de (dé)sérialisation entre les deux. La création,
lecture et mise à jour effectives des jobs — y compris l'idempotence
(ADR-5) et la réconciliation au démarrage (ADR-10) — sont la responsabilité
de gestionnaire.py (tâche suivante), pas de ce module.

Champs internes jamais exposés par GET /jobs/{job_id} (risque de fuite de
chemins serveur ou de valeurs utilisées pour l'idempotence, voir
milestone_4_api.md) : chemin_fichier_temp, dataset_hash, transaction_hash.
Voir JobPublic, qui les exclut explicitement.
"""

import enum
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer


class TypeJob(str, enum.Enum):
    RAPPORT_QUALITE = "rapport_qualite"
    RAPPORT_INTELLIGENCE = "rapport_intelligence"
    CERTIFICATION = "certification"


class StatutJob(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    ECHEC = "echec"
    ECHEC_RECUPERABLE = "echec_recuperable"


class ErreurJob(BaseModel):
    """
    Même forme que le format d'erreur HTTP uniforme du Milestone #4
    (§ "Gestion des erreurs" : {"erreur": {"code": "...", "message": "..."}}),
    réutilisée ici pour le champ "erreur" d'un job terminé en échec — choix
    de cohérence, pas explicitement dicté par un ADR, à signaler si DILANE
    préfère une autre forme.
    """

    code: str
    message: str


def _vers_iso8601_z(valeur: datetime) -> str:
    """
    Formate un datetime en UTC avec le suffixe "Z", exactement comme dans
    l'exemple de milestone_4_api.md ("2026-08-26T18:00:00Z") — le format
    par défaut de Pydantic v2 produit "+00:00", pas "Z".
    """
    valeur_utc = valeur.astimezone(timezone.utc) if valeur.tzinfo else valeur.replace(tzinfo=timezone.utc)
    return valeur_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


class Job(BaseModel):
    """
    Représentation complète d'un job, telle que stockée en base SQLite —
    inclut les champs internes. C'est cette forme que gestionnaire.py
    manipule ; JobPublic (ci-dessous) est la vue exposée par l'API.
    """

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    type: TypeJob
    statut: StatutJob = StatutJob.EN_ATTENTE
    # progression/etape restent null pour ce Milestone (ADR-4 révisée) : aucun des
    # trois modules n'expose de callback de progression réelle aujourd'hui.
    progression: Optional[float] = None
    etape: Optional[str] = None
    resultat: Optional[dict] = None
    erreur: Optional[ErreurJob] = None
    cree_le: datetime
    mis_a_jour_le: datetime

    # Champs internes au JobManager — jamais exposés via GET /jobs/{job_id} (voir JobPublic)
    chemin_fichier_temp: Optional[str] = None
    dataset_hash: Optional[str] = None
    transaction_hash: Optional[str] = None

    @field_serializer("cree_le", "mis_a_jour_le")
    def _serialiser_dates(self, valeur: datetime) -> str:
        return _vers_iso8601_z(valeur)


class JobPublic(BaseModel):
    """
    Vue exposée par GET /api/v1/jobs/{job_id} — mêmes champs que Job, à
    l'exclusion des champs internes (chemin_fichier_temp, dataset_hash,
    transaction_hash).
    """

    job_id: str
    type: TypeJob
    statut: StatutJob
    progression: Optional[float] = None
    etape: Optional[str] = None
    resultat: Optional[dict] = None
    erreur: Optional[ErreurJob] = None
    cree_le: datetime
    mis_a_jour_le: datetime

    @field_serializer("cree_le", "mis_a_jour_le")
    def _serialiser_dates(self, valeur: datetime) -> str:
        return _vers_iso8601_z(valeur)

    @classmethod
    def depuis_job(cls, job: "Job") -> "JobPublic":
        return cls(
            **job.model_dump(exclude={"chemin_fichier_temp", "dataset_hash", "transaction_hash"})
        )


def nouveau_job(type_job: TypeJob, **champs_internes) -> Job:
    """
    Construit un job fraîchement créé : job_id généré, statut "en_attente",
    cree_le == mis_a_jour_le == maintenant (UTC). champs_internes permet de
    renseigner dès la création chemin_fichier_temp/dataset_hash si connus
    (ex. ADR-6 : le fichier est déjà sauvegardé sur disque avant que le
    job_id soit renvoyé).
    """
    maintenant = datetime.now(timezone.utc)
    return Job(
        type=type_job,
        statut=StatutJob.EN_ATTENTE,
        cree_le=maintenant,
        mis_a_jour_le=maintenant,
        **champs_internes,
    )


# --- Schéma SQLite (ADR-3 : persistance sur disque, pas en mémoire) ---
#
# Colonnes dénormalisées (job_id, type, statut, dataset_hash, transaction_hash) pour permettre
# les requêtes indexées dont gestionnaire.py a besoin : idempotence par dataset_hash (ADR-5),
# réconciliation au démarrage par statut="en_cours" (ADR-10). Le reste du job (y compris les
# champs dénormalisés, par simplicité de relecture) est aussi stocké intégralement en JSON dans
# donnees_json, pour reconstruire un Job complet en une seule désérialisation.

NOM_TABLE = "jobs"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {NOM_TABLE} (
    job_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    statut TEXT NOT NULL,
    dataset_hash TEXT,
    transaction_hash TEXT,
    cree_le TEXT NOT NULL,
    mis_a_jour_le TEXT NOT NULL,
    donnees_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_statut ON {NOM_TABLE} (statut);
CREATE INDEX IF NOT EXISTS idx_jobs_dataset_hash ON {NOM_TABLE} (dataset_hash);
"""


def initialiser_schema(connexion: sqlite3.Connection) -> None:
    """Crée la table jobs et ses index si absents. Idempotent (IF NOT EXISTS)."""
    connexion.executescript(SCHEMA_SQL)
    connexion.commit()


def job_vers_ligne(job: Job) -> dict:
    """
    Sérialise un Job en dict prêt à être inséré/mis à jour dans la table
    `jobs` (clés = noms de colonnes). donnees_json contient le job complet,
    y compris ses champs internes.
    """
    return {
        "job_id": job.job_id,
        "type": job.type.value,
        "statut": job.statut.value,
        "dataset_hash": job.dataset_hash,
        "transaction_hash": job.transaction_hash,
        "cree_le": _vers_iso8601_z(job.cree_le),
        "mis_a_jour_le": _vers_iso8601_z(job.mis_a_jour_le),
        "donnees_json": job.model_dump_json(),
    }


def ligne_vers_job(ligne: sqlite3.Row) -> Job:
    """Reconstruit un Job complet à partir d'une ligne lue dans la table `jobs`."""
    return Job.model_validate_json(ligne["donnees_json"])
