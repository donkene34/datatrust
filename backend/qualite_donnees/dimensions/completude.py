"""Dimension : complétude — proportion de valeurs renseignées."""


def calculer_completude(tableau, profil):
    nb_cellules_total = profil["taille"]["lignes"] * profil["taille"]["colonnes"]

    if nb_cellules_total == 0:
        return {
            "score": 100.0,
            "statut": "non_applicable",
            "explication": "Jeu de données vide, aucune cellule à évaluer.",
            "details": {},
        }

    nb_manquants_total = sum(c["nb_manquants"] for c in profil["colonnes"])
    taux_manquants = nb_manquants_total / nb_cellules_total
    score = round(max(0.0, 100 - taux_manquants * 100), 2)

    pires_colonnes = sorted(
        [c for c in profil["colonnes"] if c["taux_manquants"] > 0],
        key=lambda c: c["taux_manquants"],
        reverse=True,
    )[:3]

    if pires_colonnes:
        detail_str = ", ".join(f"{c['nom']} ({c['taux_manquants'] * 100:.1f}%)" for c in pires_colonnes)
        explication = f"{taux_manquants * 100:.1f}% de valeurs manquantes au total. Colonnes les plus touchées : {detail_str}."
    else:
        explication = "Aucune valeur manquante détectée."

    return {
        "score": score,
        "statut": "evalue",
        "explication": explication,
        "details": {
            "taux_manquants_global": round(taux_manquants, 4),
            "colonnes_les_plus_touchees": [c["nom"] for c in pires_colonnes],
        },
    }
