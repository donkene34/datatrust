from confiance.certification import certifier_dataset, verifier_dataset

chemin_dataset = "../dataset/realworld_medical_dirty.csv"  # le plus petit dataset de démo, pour un test rapide

certificat = certifier_dataset(
    chemin_dataset,
    owner_address="0x9a4bcbf1a456a2212ebcb8e0d98a5eb5aa395a1a",
)
print(certificat)

if "erreur" not in certificat:
    resultat = verifier_dataset(chemin_dataset, certificat["dataset_id"])
    print(resultat)