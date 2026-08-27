"""
routes/insights.py — POST /api/v1/insights/rapports (Milestone #4, tâche #8).

Reçoit exclusivement {"job_id": "uuid"} référençant un job "rapport_qualite"
déjà terminé (ADR-9-bis) — jamais d'upload direct. Aucune logique métier
propre (ADR-7) : orchestration HTTP + job, et la vérification de cohérence
dataset explicitement exigée par DILANE (ADR-12).

ADR-12 (Option B) : le rapport qualité déjà calculé par le job référencé est
réutilisé (insights_ia.generer_rapport_intelligence(rapport_qualite=...)),
pour éviter un recalcul coûteux — mais seulement après avoir revérifié que
le fichier réellement présent à chemin_fichier_temp correspond encore au
dataset_hash enregistré à la création du job qualité. Une incohérence
(fichier remplacé/altéré entre-temps, ou même supprimé) est rejetée
explicitement (409 dataset_incoherent) plutôt qu'acceptée silencieusement —
c'est le risque que DILANE a nommé : "insights de B + score qualité de A"
appliqué à une plateforme de Data Trust.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from confiance.hachage import calculer_hash_fichier
from insights_ia import generer_rapport_intelligence

from ..jobs.modeles import ErreurJob, StatutJob, TypeJob
from ..schemas.insights import RequeteInsights

router = APIRouter()


def _gestionnaire():
    from ..main import gestionnaire_jobs

    return gestionnaire_jobs


def _executer_rapport_insights(job_id: str, chemin_fichier: str, rapport_qualite: dict) -> None:
    """Fonction exécutée en arrière-plan (BackgroundTasks) après la réponse 202."""
    gestionnaire = _gestionnaire()
    gestionnaire.mettre_a_jour_job(job_id, statut=StatutJob.EN_COURS)
    try:
        # rapport_qualite fourni (ADR-12, Option B) : moteur.py saute son appel interne à
        # generer_rapport() et réutilise celui-ci tel quel — voir insights_ia/moteur.py
        resultat = generer_rapport_intelligence(chemin_fichier, rapport_qualite=rapport_qualite)
    except Exception as exc:
        # generer_rapport_intelligence() ne lève jamais à cause d'un échec LLM (ADR-5 du
        # Milestone #2 : "insights_ia" contient {"erreur": ...} dans ce cas), mais peut
        # théoriquement échouer ailleurs (ex. artefact analytique, qui relit le fichier
        # séparément) — capture large pour ne jamais laisser le job bloqué "en_cours"
        gestionnaire.mettre_a_jour_job(
            job_id,
            statut=StatutJob.ECHEC,
            erreur=ErreurJob(code="rapport_intelligence_echec", message=f"{type(exc).__name__}: {exc}"),
        )
        return
    gestionnaire.mettre_a_jour_job(job_id, statut=StatutJob.TERMINE, resultat=resultat)


@router.post("/insights/rapports", status_code=202)
async def creer_rapport_insights(requete: RequeteInsights, taches_arriere_plan: BackgroundTasks):
    gestionnaire = _gestionnaire()
    job_qualite = gestionnaire.lire_job(requete.job_id)

    if job_qualite is None:
        raise HTTPException(
            status_code=404,
            detail={
                "erreur": {
                    "code": "job_introuvable",
                    "message": f"Aucun job trouvé pour l'identifiant '{requete.job_id}'.",
                }
            },
        )

    if job_qualite.type != TypeJob.RAPPORT_QUALITE:
        raise HTTPException(
            status_code=400,
            detail={
                "erreur": {
                    "code": "type_job_incorrect",
                    "message": f"Le job '{requete.job_id}' n'est pas de type rapport_qualite (type actuel : {job_qualite.type.value}).",
                }
            },
        )

    if job_qualite.statut != StatutJob.TERMINE:
        raise HTTPException(
            status_code=409,
            detail={
                "erreur": {
                    "code": "job_qualite_non_termine",
                    "message": f"Le job qualité '{requete.job_id}' n'est pas encore terminé (statut actuel : {job_qualite.statut.value}).",
                }
            },
        )

    # ADR-12 : vérification de cohérence dataset — recalcule le hash du fichier réellement
    # présent sur disque et le compare au dataset_hash enregistré à la création du job qualité.
    try:
        hash_actuel = calculer_hash_fichier(job_qualite.chemin_fichier_temp)
    except (FileNotFoundError, OSError) as exc:
        # Fichier absent (ex. déjà nettoyé) : on ne peut plus garantir la cohérence dataset —
        # traité comme une incohérence plutôt que comme une erreur serveur générique, puisque
        # le problème est bien "ce job qualité ne correspond plus à un fichier vérifiable".
        raise HTTPException(
            status_code=409,
            detail={
                "erreur": {
                    "code": "dataset_incoherent",
                    "message": f"Fichier source du job qualité introuvable ({type(exc).__name__}) — cohérence non vérifiable.",
                }
            },
        )

    if hash_actuel != job_qualite.dataset_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "erreur": {
                    "code": "dataset_incoherent",
                    "message": "Le fichier associé au job qualité a changé depuis son calcul — insights refusés pour éviter de mélanger deux datasets différents.",
                }
            },
        )

    job_insights = gestionnaire.creer_job(
        TypeJob.RAPPORT_INTELLIGENCE,
        chemin_fichier_temp=job_qualite.chemin_fichier_temp,
        dataset_hash=job_qualite.dataset_hash,
    )

    taches_arriere_plan.add_task(
        _executer_rapport_insights, job_insights.job_id, job_qualite.chemin_fichier_temp, job_qualite.resultat
    )

    return {"job_id": job_insights.job_id, "statut": job_insights.statut.value}
