"""
utilitaires_type.py — Petites aides pour détecter et nommer le type d'une
colonne de façon robuste face aux différentes versions de Pandas.

Pandas 3.x introduit un dtype `string` (`StringDtype`) dédié pour le texte,
qui s'affiche comme "str", alors que les versions plus anciennes utilisent
`object` pour la même chose. Le code des dimensions ne doit jamais comparer
un dtype à la chaîne littérale "object" ou "str" : il doit passer par
est_type_textuel(). De même, le rapport ne doit jamais exposer le nom brut
du dtype Pandas (str(serie.dtype)) : il doit passer par type_lisible(), qui
retourne toujours l'une des 5 valeurs documentées dans le contrat de données
(claude/milestone_1_coeur_data.md), quelle que soit la version de Pandas
installée sur la machine qui exécute le code.
"""

import pandas as pd


def est_type_textuel(serie):
    """Vrai si la colonne contient du texte (dtype object ou string)."""
    return pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)


def type_lisible(serie):
    """
    Traduit le dtype Pandas de la colonne vers l'une des 5 valeurs stables
    documentées dans le contrat de données : "int64", "float64", "str",
    "datetime64", "bool".

    Sans cette traduction, str(serie.dtype) renvoie "object" avec les
    versions de Pandas antérieures à 3.0 mais "str" avec Pandas 3.x pour un
    même type de colonne (texte) — un contrat de données ne doit pas changer
    de valeur selon l'environnement d'exécution.
    """
    if pd.api.types.is_bool_dtype(serie):
        return "bool"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "datetime64"
    if pd.api.types.is_integer_dtype(serie):
        return "int64"
    if pd.api.types.is_float_dtype(serie):
        return "float64"
    if est_type_textuel(serie):
        return "str"
    # Repli très improbable (ex. dtype catégoriel ou complexe non prévu) :
    # on garde le nom réel plutôt que de masquer un cas non couvert.
    return str(serie.dtype)
