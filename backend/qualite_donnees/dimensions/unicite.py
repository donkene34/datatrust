"""Dimension : unicité — détection des lignes dupliquées."""


def calculer_unicite(tableau, profil):
    nb_lignes_total = profil["taille"]["lignes"]

    if nb_lignes_total == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Jeu de données vide, aucune ligne à évaluer.",
            "details": {},
        }

    nb_doublons = int(tableau.duplicated().sum())
    taux_doublons = nb_doublons / nb_lignes_total
    score = round(max(0.0, 100 - taux_doublons * 100), 2)

    if nb_doublons > 0:
        explication = f"{nb_doublons} ligne(s) dupliquée(s) détectée(s) ({taux_doublons * 100:.1f}% du jeu de données)."
    else:
        explication = "Aucun enregistrement dupliqué détecté."

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {
            "nb_doublons": nb_doublons,
            "taux_doublons": round(taux_doublons, 4),
        },
    }
