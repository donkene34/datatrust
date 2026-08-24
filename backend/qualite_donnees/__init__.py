"""
Moteur de Qualité des Données (qualite_donnees) — Milestone #1 (Phase 1 : Cœur Data).

Point d'entrée principal : generer_rapport(chemin_fichier) -> dict
JSON-sérialisable contenant le score global, le détail par dimension (6
dimensions, chacune avec score/statut/explication) et le profil structuré
du jeu de données. Tous les identifiants, les noms de fichiers et les clés
du JSON produit sont en français.

Voir claude/milestone_1_coeur_data.md pour la spécification complète.
"""

from .rapport import generer_rapport

__all__ = ["generer_rapport"]
