"""
routes/jobs.py — GET /api/v1/jobs/{job_id} (Milestone #4, tâche #7).

Lecture d'un job existant, quel que soit son type (rapport_qualite,
rapport_intelligence, certification) — vue publique (JobPublic, voir
modeles.py), sans les champs internes (chemin_fichier_temp, dataset_hash,
transaction_hash — risque de fuite de chemins serveur). Aucune logique
métier ici (ADR-7) : lecture seule via le JobManager.
"""

from fastapi import APIRouter, HTTPException

from ..jobs.modeles import JobPublic

router = APIRouter()


def _gestionnaire():
    from ..main import gestionnaire_jobs

    return gestionnaire_jobs


@router.get("/jobs/{job_id}", response_model=JobPublic)
def lire_job(job_id: str):
    job_public = _gestionnaire().lire_job_public(job_id)
    if job_public is None:
        raise HTTPException(
            status_code=404,
            detail={
                "erreur": {
                    "code": "job_introuvable",
                    "message": f"Aucun job trouvé pour l'identifiant '{job_id}'.",
                }
            },
        )
    return job_public
