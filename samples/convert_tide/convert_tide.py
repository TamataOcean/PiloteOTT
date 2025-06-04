import re
import json

# Fonction pour convertir les marées en JSON 
# ------------------------------------------

def convertir_marées(fichier_texte, fichier_json):
    # Ouvrir le fichier texte
    with open(fichier_texte, 'r') as f:
        lignes = f.readlines()
    
    # Liste pour stocker les données converties
    donnees_marees = []

    # Expression régulière mise à jour pour capturer les différents formats
    motif = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+([\d.]+)\s+([A-Za-z]+)\s*(\d{1,3})?')

    # Parcourir toutes les lignes après l'en-tête
    for ligne in lignes[1:]:  # On saute la première ligne (entête)
        ligne = ligne.strip()  # Enlever les espaces et sauts de ligne
        if ligne:  # Si la ligne n'est pas vide
            print(f"Ligne lue : '{ligne}'")  # Afficher la ligne pour vérifier
            match = motif.match(ligne)
            if match:
                date, heure, hauteur, marée, coeff = match.groups()
                # Si le coefficient est trouvé, on l'ajoute, sinon on met None
                donnees_marees.append({
                    "date": date,
                    "heure": heure,
                    "hauteur": float(hauteur),
                    "marée": marée,
                    "coefficient": int(coeff) if coeff else None
                })
            else:
                print(f"Pas de correspondance pour : '{ligne}'")  # Afficher si la ligne ne correspond pas

    # Enregistrer les données dans le fichier JSON
    if donnees_marees:
        with open(fichier_json, 'w') as f_json:
            json.dump(donnees_marees, f_json, ensure_ascii=False, indent=4)
        print(f"Données converties et enregistrées dans {fichier_json}")
    else:
        print("Aucune donnée valide à enregistrer.")

# Appel de la fonction avec les fichiers correspondants
convertir_marées('LaRochelle_tides.txt', 'marees.json')
