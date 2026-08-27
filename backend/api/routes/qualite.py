"""
routes/qualite.py — POST /api/v1/qualite/rapports (Milestone #4, tâche #6).

Upload d'un fichier CSV → job asynchrone "rapport_qualite" (ADR-1), qui
appelle qualite_donnees.generer_rapport() une fois exécuté en arrière-plan.
Aucune logique métier ici (ADR-7) : uniquement l'orchestration HTTP + job.

ADR-6 : le fichier est lu et sauvegardé sur disque de façon synchrone dans
ce handler, avant que le job_id soit renvoyé — un UploadFile est un flux lié
à la requête, indisponible pour une tâche BackgroundTasks après la réponse.

ADR-9 : le fichier temporaire est nommé par un UUID généré ici, jamais par
le nom fourni par l'utilisateur (traversée de chemin).

ADR-12 : le hash du fichier (dataset_hash) est calculé et stocké sur le job
dès sa création — nécessaire à la vérification de cohérence dataset que
/insights/rapports effectuera plus tard (tâche #8), avant de réutiliser ce
rapport qualité.
"""

import os
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from confiance.hachage import calculer_hash_fichier
from qualite_donnees import generer_rapport

from ..jobs.modeles import ErreurJob, StatutJob, TypeJob

router = APIRouter()


def _gestionnaire_et_dossier_uploads():
    """
    Import différé de l'instance JobManager et du dossier d'uploads partagés,
    définis dans main.py — évite un import circulaire (main monte ce router,
    donc importe qualite.py ; qualite.py ne doit pas importer main.py au
    chargement du module, seulement au moment de l'appel).
    """
    from ..main import DOSSIER_UPLOADS_TEMP, gestionnaire_jobs

    return gestionnaire_jobs, DOSSIER_UPLOADS_TEMP


def _executer_rapport_qualite(job_id: str, chemin_fichier: str) -> None:
    """Fonction exécutée en arrière-plan (BackgroundTasks) après la réponse 202."""
    gestionnaire, _ = _gestionnaire_et_dossier_uploads()
    gestionnaire.mettre_a_jour_job(job_id, statut=StatutJob.EN_COURS)
    try:
        rapport = generer_rapport(chemin_fichier)
    except Exception as exc:
        # qualite_donnees lève des exceptions standard (ex. ValueError pour un CSV illisible),
        # contrairement aux modules confiance/insights_ia qui retournent {"erreur": ...} —
        # capture large à cette frontière pour ne jamais laisser un job bloqué "en_cours" (ADR-6
        # du Milestone #3, même principe appliqué ici au niveau job)
        gestionnaire.mettre_a_jour_job(
            job_id,
            statut=StatutJob.ECHEC,
            erreur=ErreurJob(code="rapport_qualite_echec", message=f"{type(exc).__name__}: {exc}"),
        )
        return
    gestionnaire.mettre_a_jour_job(job_id, statut=StatutJob.TERMINE, resultat=rapport)


@router.post("/qualite/rapports", status_code=202)
async def creer_rapport_qualite(taches_arriere_plan: BackgroundTasks, fichier: UploadFile = File(...)):
    if not fichier.filename:
        raise HTTPException(
            status_code=400, detail={"erreur": {"code": "fichier_absent", "message": "Aucun fichier fourni."}}
        )

    contenu = await fichier.read()  # ADR-6 : lecture synchrone avant la réponse
    if not contenu:
        raise HTTPException(
            status_code=400,
            detail={"erreur": {"code": "fichier_invalide", "message": "Le fichier envoyé est vide."}},
        )

    gestionnaire, dossier_uploads = _gestionnaire_et_dossier_uploads()
    os.makedirs(dossier_uploads, exist_ok=True)

    # ADR-9 : nom généré par l'application, jamais le nom fourni par l'utilisateur ni son
    # extension d'origine — l'extension .csv est fixe (périmètre du MVP : CSV uniquement).
    chemin_fichier_temp = os.path.join(dossier_uploads, f"{uuid.uuid4()}.csv")
    with open(chemin_fichier_temp, "wb") as flux:
        flux.write(contenu)

    dataset_hash = calculer_hash_fichier(chemin_fichier_temp)  # ADR-12 : nécessaire à /insights/rapports plus tard

    job = gestionnaire.creer_job(
        TypeJob.RAPPORT_QUALITE,
        chemin_fichier_temp=chemin_fichier_temp,
        dataset_hash=dataset_hash,
    )

    taches_arriere_plan.add_task(_executer_rapport_qualite, job.job_id, chemin_fichier_temp)

    return {"job_id": job.job_id, "statut": job.statut.value}
