"""
schemas/insights.py — Modèle de requête pour POST /api/v1/insights/rapports
(Milestone #4, tâche #8). Voir ADR-9-bis : le corps ne contient qu'une
référence à un job "rapport_qualite" déjà terminé, jamais un upload direct.
"""

from pydantic import BaseModel


class RequeteInsights(BaseModel):
    job_id: str
