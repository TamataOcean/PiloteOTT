import re
import json
from datetime import datetime, timezone
import bisect

# Fonction pour convertir les marées en JSON
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

# Fonction pour déterminer l'état de la marée
def etat_maree(fichier_json):
    # Charger les données des marées depuis le fichier JSON
    with open(fichier_json, 'r') as f_json:
        marees = json.load(f_json)

    # Convertir les données en objets datetime avec timezone UTC
    marees = [(datetime.strptime(m["date"] + " " + m["heure"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc), m["hauteur"], m["marée"]) for m in marees]

    # Obtenir la date et l'heure actuelles en UTC
    now = datetime.now(timezone.utc)
    # Modifier l'heure actuelle à une date et heure spécifique
    #now = datetime(2025, 4, 2, 6, 20, tzinfo=timezone.utc)  # Exemple: 2 avril 2025 à 04h20 UTC
    sprint(f"now = {now}")

    # Extraire uniquement les horaires pour recherche rapide
    times = [m[0] for m in marees]

    # Trouver l'index où insérer l'heure actuelle
    index = bisect.bisect(times, now)

    if index == 0:
        print("L'heure actuelle est avant les premières données. Impossible de déterminer la marée.")
    elif index == len(marees):
        print("L'heure actuelle est après les dernières données. Impossible de déterminer la marée.")
    else:
        prev_maree = marees[index - 1]
        next_maree = marees[index]

        if prev_maree[2] == "BM" and next_maree[2] == "PM":
            print("La marée est montante.")
        elif prev_maree[2] == "PM" and next_maree[2] == "BM":
            print("La marée est descendante.")
        else:
            print("Erreur dans les données des marées.")

# Appel de la fonction pour convertir les données du fichier texte en JSON
#convertir_marées('LaRochelle_tides.txt', 'marees.json')
convertir_marées('Maree-6h6h.txt', 'marees.json')

# Appel de la fonction pour déterminer l'état de la marée à l'instant actuel
etat_maree('marees.json')
