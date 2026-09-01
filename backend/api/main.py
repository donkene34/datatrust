"""
main.py — Point d'entrée FastAPI (Milestone #4, Phase 4a : API Backend).

Instancie l'application, configure CORS (pour le futur frontend Next.js,
origine différente en développement, voir milestone_4_api.md § Contraintes),
et déclenche la réconciliation des jobs au démarrage (ADR-10). Ce fichier
n'implémente aucune logique métier lui-même (ADR-7) : le JobManager
(gestionnaire.py) et les modules déjà validés (qualite_donnees, insights_ia,
confiance) portent toute la logique.

Les routers (routes/qualite.py, routes/insights.py, routes/certifications.py,
routes/jobs.py) sont montés au fur et à mesure de leur construction (tâches
suivantes) — voir le bloc en bas de ce fichier.

Variables d'environnement (optionnelles, valeurs par défaut adaptées au
développement local) :
- JOBS_DB_PATH : chemin du fichier SQLite de suivi des jobs (ADR-3).
  Par défaut : backend/api/jobs.db, à côté de ce fichier.
- CORS_ORIGINS : liste d'origines autorisées, séparées par des virgules.
  Par défaut : http://localhost:3000 (le futur frontend Next.js en dev).
- UPLOADS_TEMP_DIR : dossier des fichiers uploadés temporaires (ADR-9).
  Par défaut : backend/api/uploads_temp, à côté de ce fichier.
- UPLOAD_TTL_HOURS : durée de rétention (en heures) des fichiers temporaires
  liés à un job terminé/en échec, avant nettoyage (ADR-9). Par défaut : 24.
  Un fichier lié à un job en_attente/en_cours n'est jamais supprimé, quel
  que soit son âge (critère #14) — voir gestionnaire.py::nettoyer_fichiers_expires().

Gestion des erreurs (§ "Gestion des erreurs" de milestone_4_api.md) : deux
gestionnaires d'exception globaux reformattent toute erreur 4xx/5xx au
format uniforme {"erreur": {"code", "message"}}, pour que les routes
(tâches #6 à #9) puissent lever une HTTPException avec un detail déjà sous
cette forme, ou laisser une erreur de validation FastAPI native être
reformattée automatiquement — ce n'est pas de la logique métier (ADR-7),
uniquement la mise en forme HTTP commune à toutes les routes.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .jobs.gestionnaire import JobManager

load_dotenv()  # même mécanisme que le reste du projet — n'écrase jamais une variable déjà définie

CHEMIN_BDD_JOBS = os.environ.get(
    "JOBS_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")
)
DOSSIER_UPLOADS_TEMP = os.environ.get(
    "UPLOADS_TEMP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads_temp")
)
DUREE_TTL_UPLOADS_HEURES = float(os.environ.get("UPLOAD_TTL_HOURS", "24"))
ORIGINES_CORS = [
    origine.strip()
    for origine in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origine.strip()
]

gestionnaire_jobs = JobManager(CHEMIN_BDD_JOBS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ADR-9 : le dossier des fichiers temporaires doit exister avant la première requête.
    os.makedirs(DOSSIER_UPLOADS_TEMP, exist_ok=True)
    # ADR-10 : tout job trouvé "en_cours" au démarrage (crash précédent, serveur
    # relancé) est réconcilié — voir gestionnaire.py::reconcilier_au_demarrage()
    # pour le détail des 3 issues possibles (termine / echec / echec_recuperable).
    # Exécuté AVANT le nettoyage ci-dessous, pour que celui-ci voie le statut à
    # jour des jobs (un job qu'on vient de reconnaître en_cours ne doit pas être
    # traité comme terminé par erreur).
    resume = gestionnaire_jobs.reconcilier_au_demarrage()
    if resume:
        print(f"[réconciliation au démarrage] {len(resume)} job(s) en_cours traité(s) : {resume}")

    # ADR-9 : nettoyage des fichiers temporaires expirés — déclenché une fois au démarrage
    # (pas de tâche planifiée périodique pour ce MVP, même limite assumée que la réconciliation).
    chemins_supprimes = gestionnaire_jobs.nettoyer_fichiers_expires(DUREE_TTL_UPLOADS_HEURES)
    if chemins_supprimes:
        print(f"[nettoyage au démarrage] {len(chemins_supprimes)} fichier(s) temporaire(s) expiré(s) supprimé(s).")

    yield


app = FastAPI(title="Data Trust & Insights — API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINES_CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def gestion_http_exception(request: Request, exc: HTTPException):
    """
    Reformate toute HTTPException en {"erreur": {"code", "message"}} (format
    uniforme). Si une route construit déjà son detail sous cette forme
    (le cas normal, ex. HTTPException(status_code=404, detail={"erreur": {...}})),
    il est repris tel quel ; sinon (ex. HTTPException(status_code=404) brute)
    il est enveloppé automatiquement avec un code générique.
    """
    if isinstance(exc.detail, dict) and "erreur" in exc.detail:
        corps = exc.detail
    else:
        corps = {"erreur": {"code": "erreur_http", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=corps)


@app.exception_handler(RequestValidationError)
async def gestion_erreur_validation(request: Request, exc: RequestValidationError):
    """Erreur de validation FastAPI/Pydantic native (ex. partie multipart manquante) — même format uniforme."""
    return JSONResponse(
        status_code=422,
        content={"erreur": {"code": "requete_invalide", "message": str(exc.errors())}},
    )


@app.get("/api/v1/health")
def sante():
    return {"statut": "ok"}


# Montage des routers : les 4 du Milestone #4 (tâches #6 à #9), plus datasets.py (Milestone #4.1) :
from .routes import certifications, datasets, insights
from .routes import jobs as jobs_routes
from .routes import qualite

app.include_router(qualite.router, prefix="/api/v1")
app.include_router(jobs_routes.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
app.include_router(certifications.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
