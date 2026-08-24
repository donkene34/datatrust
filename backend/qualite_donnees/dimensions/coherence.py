"""
Dimension : cohérence — uniformité de format des valeurs catégorielles
au sein d'une même colonne (ex. "Male" / "male" / "MALE" représentant la
même valeur écrite de façons différentes).

Distincte de validity.py : ici on ne juge pas si une valeur est "invalide",
seulement si des valeurs équivalentes sont écrites de manière incohérente.
Ne s'applique qu'aux colonnes à faible cardinalité (catégorielles) — une
colonne de texte libre ou d'identifiants est ignorée (statut "non_applicable"
si aucune colonne catégorielle n'est trouvée dans tout le jeu de données).
"""

from ..utilitaires_type import est_type_textuel


def _ressemble_a_categorielle(serie, infos_colonne, nb_lignes):
    if not est_type_textuel(serie):
        return False
    if nb_lignes == 0:
        return False
    # Beaucoup de valeurs distinctes par rapport au nombre de lignes -> texte libre / identifiant, pas catégoriel
    if infos_colonne["nb_valeurs_uniques"] > 50 and (infos_colonne["nb_valeurs_uniques"] / nb_lignes) > 0.5:
        return False
    return True


def calculer_coherence(tableau, profil):
    nb_lignes = profil["taille"]["lignes"]
    problemes = []
    cellules_affectees = 0
    cellules_categorielles_total = 0

    for infos_colonne in profil["colonnes"]:
        if not _ressemble_a_categorielle(tableau[infos_colonne["nom"]], infos_colonne, nb_lignes):
            continue

        colonne = infos_colonne["nom"]
        serie = tableau[colonne].dropna().astype(str)
        if len(serie) == 0:
            continue

        cellules_categorielles_total += len(serie)

        groupes_normalises = {}
        for valeur in serie:
            cle = valeur.strip().lower()
            groupes_normalises.setdefault(cle, set()).add(valeur)

        cles_incoherentes = {k for k, variantes in groupes_normalises.items() if len(variantes) > 1}
        if cles_incoherentes:
            serie_normalisee = serie.str.strip().str.lower()
            affectees = int(serie_normalisee.isin(cles_incoherentes).sum())
            cellules_affectees += affectees
            exemples = [sorted(groupes_normalises[k]) for k in list(cles_incoherentes)[:2]]
            problemes.append(f"{colonne}: variantes d'écriture incohérentes pour une même valeur (ex. {exemples})")

    if cellules_categorielles_total == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Aucune colonne catégorielle détectée pour évaluer la cohérence de format.",
            "details": {},
        }

    taux = cellules_affectees / cellules_categorielles_total
    score = round(max(0.0, 100 - taux * 100), 2)
    explication = "; ".join(problemes[:3]) if problemes else "Formats cohérents sur toutes les colonnes catégorielles détectées."

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {"problemes": problemes},
    }
