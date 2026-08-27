"""
routes/certifications.py — les 3 endpoints de certification (Milestone #4,
tâche #9) : POST /api/v1/certifications, GET /api/v1/certifications/{dataset_id},
POST /api/v1/certifications/{dataset_id}/verifier.

Aucune logique métier propre (ADR-7) : orchestration HTTP + job, appelle
uniquement confiance.certifier_dataset()/obtenir_certificat()/verifier_dataset()
déjà validés au Milestone #3. L'idempotence à 3 cas (ADR-5) est implémentée
dans gestionnaire.py (tâche #4), pas ici.

Limite connue, signalée plutôt que masquée : confiance.certifier_dataset()
n'expose aucun callback intermédiaire — il envoie la transaction ET attend
sa confirmation dans le même appel bloquant. Le job.transaction_hash
(nécessaire à ADR-10 pour la réconciliation après crash) n'est donc connu
qu'APRÈS confirmation, jamais "dès l'envoi" comme le décrit littéralement
milestone_4_api.md § Cycle de vie d'un job. Un crash survenant précisément
pendant l'attente de confirmation (fenêtre de quelques secondes à quelques
dizaines de secondes, mesures du Milestone #3) laisse donc ce job sans
transaction_hash au redémarrage : il sera marqué echec_recuperable
directement (au lieu d'être vérifié via obtenir_recu_transaction()), ce qui
reste sûr (une nouvelle tentative est autorisée, ADR-10 point 4) mais moins
précis que l'idéal. Corriger cela demanderait d'ajouter un callback optionnel
à confiance.client_blockchain.certifier() (changement additif, à faire
approuver explicitement — pas fait ici, confiance/ n'est pas touché par
cette tâche).
"""

import os
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from confiance import certifier_dataset, verifier_dataset
from confiance.client_blockchain import obtenir_certificat
from confiance.hachage import calculer_hash_fichier

from ..jobs.modeles import ErreurJob, StatutJob, TypeJob

router = APIRouter()


def _gestionnaire_et_dossier_uploads():
    from ..main import DOSSIER_UPLOADS_TEMP, gestionnaire_jobs

    return gestionnaire_jobs, DOSSIER_UPLOADS_TEMP


def _code_erreur_certification(message: str) -> str:
    """
    confiance.certifier_dataset() ne retourne pas de code d'erreur structuré,
    seulement un message texte qui préfixe la nature de l'échec (voir
    certification.py) — ce mappage reprend "tels quels" les deux codes
    prévus par milestone_4_api.md § Gestion des erreurs, sans réinterpréter
    la logique métier elle-même.
    """
    message_minuscule = message.lower()
    if "ipfs" in message_minuscule:
        return "upload_ipfs_echec"
    if "on-chain" in message_minuscule or "blockchain" in message_minuscule or "transaction" in message_minuscule:
        return "transaction_blockchain_echec"
    return "certification_echec"


def _executer_certification(job_id: str, chemin_fichier: str, owner_address: str, version: int) -> None:
    """Fonction exécutée en arrière-plan (BackgroundTasks) après la réponse 202."""
    gestionnaire, _ = _gestionnaire_et_dossier_uploads()
    gestionnaire.mettre_a_jour_job(job_id, statut=StatutJob.EN_COURS)
    try:
        resultat = certifier_dataset(chemin_fichier, owner_address, version=version)
    except Exception as exc:
        # certifier_dataset() ne lève normalement jamais (ADR-6 du Milestone #3 : {"erreur": ...}
        # en cas d'échec) — filet de sécurité pour ne jamais laisser le job bloqué "en_cours"
        gestionnaire.mettre_a_jour_job(
            job_id,
            statut=StatutJob.ECHEC,
            erreur=ErreurJob(code="certification_echec", message=f"{type(exc).__name__}: {exc}"),
        )
        return

    if "erreur" in resultat:
        gestionnaire.mettre_a_jour_job(
            job_id,
            statut=StatutJob.ECHEC,
            erreur=ErreurJob(code=_code_erreur_certification(resultat["erreur"]), message=resultat["erreur"]),
        )
        return

    gestionnaire.mettre_a_jour_job(
        job_id,
        statut=StatutJob.TERMINE,
        resultat=resultat,
        transaction_hash=resultat["hash_transaction"],
    )


@router.post("/certifications")
async def creer_certification(
    taches_arriere_plan: BackgroundTasks,
    fichier: UploadFile = File(...),
    owner_address: str = Form(...),
    version: int = Form(1),
):
    if not fichier.filename:
        raise HTTPException(
            status_code=400, detail={"erreur": {"code": "fichier_absent", "message": "Aucun fichier fourni."}}
        )

    contenu = await fichier.read()  # ADR-6 : lecture synchrone avant toute réponse
    if not contenu:
        raise HTTPException(
            status_code=400,
            detail={"erreur": {"code": "fichier_invalide", "message": "Le fichier envoyé est vide."}},
        )

    gestionnaire, dossier_uploads = _gestionnaire_et_dossier_uploads()
    os.makedirs(dossier_uploads, exist_ok=True)

    # ADR-9 : nom généré par l'application. Le hash doit être calculé avant de savoir si ce fichier
    # a déjà été certifié (idempotence, ADR-5) — ce fichier temporaire reste donc écrit même dans
    # les cas (a)/(b) ci-dessous où il ne sera finalement rattaché à aucun job ; son nettoyage
    # éventuel (fichier orphelin, jamais référencé par un job) relève de la tâche #10.
    chemin_fichier_temp = os.path.join(dossier_uploads, f"{uuid.uuid4()}.csv")
    with open(chemin_fichier_temp, "wb") as flux:
        flux.write(contenu)

    dataset_hash = calculer_hash_fichier(chemin_fichier_temp)

    cas, job_existant = gestionnaire.verifier_idempotence_certification(dataset_hash)

    if cas == "termine":
        # ADR-5 cas (a) : certificat déjà terminé pour ce hash — son résultat est retourné
        # directement, aucun nouveau job, aucune nouvelle transaction.
        return JSONResponse(status_code=200, content=job_existant.resultat)

    if cas == "en_cours":
        # ADR-5 cas (b) : le statut réel du job (en_attente ou en_cours) est renvoyé tel quel,
        # plutôt que de figer "en_cours" comme le suggère l'exemple du spec — plus honnête si le
        # job existant n'a en réalité pas encore commencé à s'exécuter.
        return JSONResponse(
            status_code=200, content={"job_id": job_existant.job_id, "statut": job_existant.statut.value}
        )

    # cas == "nouvelle_tentative" (ADR-5 cas (c), ou premier essai pour ce hash)
    job = gestionnaire.creer_job(
        TypeJob.CERTIFICATION,
        chemin_fichier_temp=chemin_fichier_temp,
        dataset_hash=dataset_hash,
    )
    taches_arriere_plan.add_task(_executer_certification, job.job_id, chemin_fichier_temp, owner_address, version)
    return JSONResponse(status_code=202, content={"job_id": job.job_id, "statut": job.statut.value})


@router.get("/certifications/{dataset_id}")
def lire_certification(dataset_id: int):
    """Lecture synchrone on-chain (gratuite, pas de transaction) — aucun job."""
    resultat = obtenir_certificat(dataset_id)
    if "erreur" in resultat:
        raise HTTPException(
            status_code=404,
            detail={
                "erreur": {
                    "code": "dataset_introuvable",
                    "message": f"Aucun certificat trouvé pour dataset_id={dataset_id}.",
                }
            },
        )
    return resultat


@router.post("/certifications/{dataset_id}/verifier")
async def verifier_certification(dataset_id: int, fichier: UploadFile = File(...)):
    """
    Synchrone (ADR-4) : pas de job créé, pas de job_id renvoyé — la
    vérification est quasi instantanée (hash + lecture on-chain gratuite).
    """
    if not fichier.filename:
        raise HTTPException(
            status_code=400, detail={"erreur": {"code": "fichier_absent", "message": "Aucun fichier fourni."}}
        )

    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(
            status_code=400,
            detail={"erreur": {"code": "fichier_invalide", "message": "Le fichier envoyé est vide."}},
        )

    _, dossier_uploads = _gestionnaire_et_dossier_uploads()
    os.makedirs(dossier_uploads, exist_ok=True)
    chemin_fichier_temp = os.path.join(dossier_uploads, f"{uuid.uuid4()}.csv")
    with open(chemin_fichier_temp, "wb") as flux:
        flux.write(contenu)

    try:
        resultat = verifier_dataset(chemin_fichier_temp, dataset_id)
    finally:
        # Pas de job asynchrone ici : rien ne référence plus ce fichier une fois la réponse
        # envoyée (ADR-9, esprit) — supprimé immédiatement plutôt que laissé pour le nettoyage TTL.
        if os.path.exists(chemin_fichier_temp):
            os.remove(chemin_fichier_temp)

    if "erreur" in resultat:
        raise HTTPException(
            status_code=404,
            detail={
                "erreur": {
                    "code": "dataset_introuvable",
                    "message": resultat["erreur"],
                }
            },
        )

    return {
        "identique": resultat["resultat"] == "IDENTIQUE",
        "dataset_id": resultat["dataset_id"],
        "hash_recalcule": resultat["hash_recalcule"],
        "hash_certifie": resultat["certificat"]["dataset_hash"],
    }
