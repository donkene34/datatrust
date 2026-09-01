"""
routes/datasets.py — GET /api/v1/datasets/{dataset_id} (Milestone #4.1).

Endpoint agrégé pour la page de détail du Milestone #5 (Phase 4b) :
combine le certificat on-chain (déjà exposé par GET /certifications/{id},
inchangé) avec les rapports qualité/insights qui ont précédé la
certification, retrouvés via la relation persistée par
routes/certifications.py::_executer_certification() au moment où le job de
certification aboutit (voir gestionnaire.py::resoudre_jobs_lies()).

Ne remplace pas GET /api/v1/certifications/{dataset_id} (lecture on-chain
seule) — s'ajoute à côté. Aucune logique métier propre (ADR-7) : orchestration
de lectures déjà exposées par confiance et par le JobManager.
"""

from fastapi import APIRouter, HTTPException

from confiance.client_blockchain import obtenir_certificat

router = APIRouter()


def _gestionnaire():
    from ..main import gestionnaire_jobs

    return gestionnaire_jobs


@router.get("/datasets/{dataset_id}")
def lire_dataset(dataset_id: int):
    """
    qualite/insights valent None quand aucun job correspondant n'a été retrouvé
    pour ce dataset — cas légitime (ex. certification faite sans étape qualité
    préalable, ou dataset certifié avant l'introduction du Milestone #4.1), pas
    une erreur : seul un certificat introuvable produit un 404.
    """
    certificat = obtenir_certificat(dataset_id)
    if "erreur" in certificat:
        raise HTTPException(
            status_code=404,
            detail={
                "erreur": {
                    "code": "dataset_introuvable",
                    "message": f"Aucun certificat trouvé pour dataset_id={dataset_id}.",
                }
            },
        )

    gestionnaire = _gestionnaire()
    job_certification = gestionnaire.trouver_job_certification_par_dataset_id(dataset_id)

    rapport_qualite = None
    rapport_insights = None
    if job_certification is not None:
        if job_certification.job_qualite_id:
            job_qualite = gestionnaire.lire_job(job_certification.job_qualite_id)
            rapport_qualite = job_qualite.resultat if job_qualite else None
        if job_certification.job_insights_id:
            job_insights = gestionnaire.lire_job(job_certification.job_insights_id)
            rapport_insights = job_insights.resultat if job_insights else None

    return {
        "dataset_id": dataset_id,
        "certificat": certificat,
        "qualite": rapport_qualite,
        "insights": rapport_insights,
    }
