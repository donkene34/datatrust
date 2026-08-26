"""
AI Insights Engine (insights_ia) — Milestone #2 (Phase 2 : Intelligence).

Point d'entrée principal : generer_rapport_intelligence(chemin_fichier) -> dict
JSON-sérialisable combinant qualité (Milestone #1, inchangé), anomalies
multivariées (Isolation Forest), visualisations (histogramme + heatmap de
corrélations) et insights générés par LLM (Groq).

Voir claude/milestone_2_intelligence.md pour la spécification complète.
"""

from .moteur import generer_rapport_intelligence

__all__ = ["generer_rapport_intelligence"]
