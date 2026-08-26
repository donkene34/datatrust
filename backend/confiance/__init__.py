"""
Module Confiance (confiance) — Milestone #3 (Phase 3 : Confiance).

Points d'entrée principaux :
- certifier_dataset(chemin_fichier, owner_address, ...) -> dict certificat complet
- verifier_dataset(chemin_fichier_recupere, dataset_id) -> dict résultat de vérification

Voir claude/milestone_3_confiance.md pour la spécification complète.
"""

from .certification import certifier_dataset, verifier_dataset

__all__ = ["certifier_dataset", "verifier_dataset"]
