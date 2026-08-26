"""
hachage.py — Empreintes cryptographiques du module confiance (Milestone #3).

ADR-1 : datasetHash = SHA-256 du contenu brut du fichier (octets), calculé
via hashlib et lu par blocs pour rester efficace en mémoire même sur de gros
fichiers (le dataset énergie fait ~133 Mo) — jamais chargé entièrement en
mémoire pour ce seul calcul.

ADR-2 / ADR-11 : metadataHash = SHA-256 d'une sérialisation JSON canonique
et déterministe de l'objet métadonnées {nom_fichier, score_global,
scores_dimensions, date_certification} : clés triées, encodage UTF-8,
précision numérique fixe, dates ISO 8601 UTC, aucun espace superflu. Deux
appels avec les mêmes métadonnées doivent toujours produire le même hash,
quel que soit l'ordre de construction du dict en amont.
"""

import hashlib
import json

TAILLE_BLOC_OCTETS = 1024 * 1024  # 1 Mo par bloc — évite de charger tout le fichier en mémoire
PRECISION_DECIMALES = 4  # nombre de décimales conservées pour les valeurs numériques avant hachage —
                          # choix d'implémentation non fixé explicitement par l'ADR-11 (qui demande une
                          # "précision numérique fixe" sans préciser laquelle) ; 4 décimales couvrent
                          # largement la précision utile d'un score_global/scores_dimensions à signaler à DILANE


def calculer_hash_fichier(chemin_fichier):
    """
    Calcule le SHA-256 du contenu brut d'un fichier (ADR-1), lu par blocs.

    Retourne le condensé sous forme hexadécimale (64 caractères), identique
    à ce que produirait `sha256sum` sur le même fichier (critère
    d'acceptation #1).
    """
    hacheur = hashlib.sha256()
    with open(chemin_fichier, "rb") as flux:
        while True:
            bloc = flux.read(TAILLE_BLOC_OCTETS)
            if not bloc:
                break
            hacheur.update(bloc)
    return hacheur.hexdigest()


def _arrondir_recursivement(valeur):
    """
    Parcourt récursivement une structure (dict/liste/valeur) et arrondit
    toute valeur flottante à PRECISION_DECIMALES décimales, pour garantir
    un hash reproductible même si la valeur d'origine provient de calculs
    numpy/pandas dont la représentation flottante peut varier légèrement
    d'un appel à l'autre (Milestone #1/#2 utilisent numpy/pandas).
    """
    if isinstance(valeur, dict):
        return {cle: _arrondir_recursivement(sous_valeur) for cle, sous_valeur in valeur.items()}
    if isinstance(valeur, list):
        return [_arrondir_recursivement(element) for element in valeur]
    if isinstance(valeur, float):
        return round(valeur, PRECISION_DECIMALES)
    return valeur


def _serialiser_canonique(objet_metadonnees):
    """
    Sérialise l'objet métadonnées en JSON canonique (ADR-11) : clés triées
    par ordre alphabétique, séparateurs sans espace superflu, encodage
    ASCII pur (ensure_ascii=True — les caractères non-ASCII sont échappés
    en \\uXXXX, ce qui rend le résultat indépendant de toute variation
    d'encodage selon la plateforme), valeurs numériques arrondies à
    précision fixe.
    """
    objet_normalise = _arrondir_recursivement(objet_metadonnees)
    return json.dumps(objet_normalise, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def calculer_hash_metadonnees(objet_metadonnees):
    """
    Calcule le SHA-256 (ADR-2, ADR-11) de la sérialisation JSON canonique de
    l'objet métadonnées structuré attendu :
    {nom_fichier, score_global, scores_dimensions, date_certification}.

    date_certification doit déjà être une chaîne ISO 8601 UTC (ex.
    "2026-08-26T14:32:00Z") au moment de l'appel — ce module ne formate pas
    les dates, il sérialise et hache ce qu'on lui fournit tel quel.

    Retourne le condensé sous forme hexadécimale (64 caractères).
    """
    chaine_canonique = _serialiser_canonique(objet_metadonnees)
    return hashlib.sha256(chaine_canonique.encode("utf-8")).hexdigest()
