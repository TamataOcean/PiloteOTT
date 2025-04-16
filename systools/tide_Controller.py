import RPi.GPIO as GPIO
import threading
import time
import requests
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import bisect

# Configuration MQTT
MQTT_BROKER =       "localhost"
# MQTT_BROKER = "host.docker.internal" # Version Dockerisé 
MQTT_PUMP_STATE =   "server/pumpState"
MQTT_LOG_GENERAL =  "server/log"
MQTT_TIDE_STATE =   "server/tideState"

MQTT_DATA =         "input/data/#"
MQTT_ORDERS =       "input/orders"
MQTT_PORT =         1883

# Chargement du fichier de configuration
CONFIG_PATH = "./config/config_PilotOTT.json"
MAREES_PATH = "./tides/marees.json"  # Chemin vers le fichier JSON des marées

global etat_pompes_local
data_capteurs = {}

def charger_configuration():
    try:
        with open(CONFIG_PATH, "r") as fichier:
            print("Fichier de configuration trouvé")
            return json.load(fichier)["conf"]
    except Exception as e:
        print(f"Erreur lors du chargement du fichier de config : {e}")
        return None

# Charger les données des marées
def charger_marees():
    try:
        with open(MAREES_PATH, "r") as fichier_marees:
            print("Fichier des marées trouvé")
            return json.load(fichier_marees)
    except Exception as e:
        print(f"Erreur lors du chargement du fichier des marées : {e}")
        return []

# Convertir les données des marées en objets datetime
def convertir_marees(marees):
    marees_converties = []
    for m in marees:
        date_heure = datetime.strptime(f"{m['date']} {m['heure']}", "%Y-%m-%d %H:%M")
        marees_converties.append({
            "datetime": date_heure,
            "hauteur": m["hauteur"],
            "marée": m["marée"],
            "coefficient": m["coefficient"]
        })
    return marees_converties

# -----------------------
# Initialisation des GPIO
# -----------------------
def initialiser_pompes():


    GPIO.setmode(GPIO.BCM)
    message = []

    for pompe in config_pilotOTT["pompes"]:
        etat_pompe = 1 if pompe['etat_initial'] == "ON" else 0
        etat_pompes_local[pompe["ID"]] = etat_pompe  # Stocker l'état initial localement
        GPIO.setup(pompe["gpio"], GPIO.OUT)
        GPIO.output(pompe["gpio"], GPIO.LOW if etat_pompe else GPIO.HIGH)

        print(f"🔧 Initialisation {pompe['ID']} ({pompe['description']}) -> {pompe['etat_initial']}")
        message.append({"ID": pompe["ID"], "pump_State": etat_pompe})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    client.publish(MQTT_LOG_GENERAL, json.dumps({"event": "Etat des pompes au démarrage", "data": message}))

# ------------------------------------------
# Contrôle des pompes en fonction des marées
# ------------------------------------------
def controler_pompes(type_maree):
    print("Function Controler_Pompes begin")
    etats_pompes = {
        "BM": {"Pompe1": "ON", "Pompe2": "OFF", "Pompe3": "ON", "Pompe4": "OFF", "Pompe5": "ON"},
        "PM": {"Pompe1": "OFF", "Pompe2": "ON", "Pompe3": "OFF", "Pompe4": "ON", "Pompe5": "OFF"}
    }
    
    if type_maree not in etats_pompes:
        print("❌ Aucune action.")
        return
    
    etat_actuel = etats_pompes[type_maree]
    message = []
    
    for pompe in config_pilotOTT["pompes"]:
        etat_pompe = 1 if etat_actuel.get(pompe["ID"], "OFF") == "ON" else 0
        GPIO.output(pompe["gpio"], GPIO.LOW if etat_pompe else GPIO.HIGH)
        print(f"🔧 {pompe['ID']} -> {'ON' if etat_pompe else 'OFF'}")
        etat_pompes_local[pompe["ID"]] = etat_pompe
        message.append({"ID": pompe["ID"], "pump_State": etat_pompe})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)

# ---------------------------------------------------------------------
# Marée Montante / Descendante en fonction de la date et heure actuelle
# ---------------------------------------------------------------------
def getMaree():
    # Récupérer l'heure actuelle
    now = datetime.now()
    print(f"Heure actuelle : {now}")

    message = []

    # Trouver les marées avant et après l'heure actuelle
    prev_maree = None
    next_maree = None

    for i in range(1, len(marees_converties)):
        if marees_converties[i]["datetime"] > now:
            next_maree = marees_converties[i]
            prev_maree = marees_converties[i - 1]
            break

    if prev_maree and next_maree:
        # Déterminer si la marée est montante ou descendante
        if prev_maree["marée"] == "BM" and next_maree["marée"] == "PM":
            # print("La marée est montante (PM).")
            type_maree = "PM"
        elif prev_maree["marée"] == "PM" and next_maree["marée"] == "BM":
            # print("La marée est descendante (BM).")
            type_maree = "BM"
        else:
            print("❌ Erreur dans les données des marées.")
            return None
        
        # Création du message JSON
        # Récupérer l'heure de la prochaine marée
        next_maree_time = next_maree["datetime"].strftime("%H:%M:%S")  # Format de l'heure HH:MM:SS


        message = {"typeMaree": type_maree, "nextTide": next_maree_time }
        json_message = json.dumps(message)
        # Publication MQTT
        client.publish(MQTT_TIDE_STATE, json_message)
        print(f"📡 Envoi état marée : {json_message}")

        return type_maree
    
    else:
        print(f"❌ Aucune donnée de marée trouvée pour l'heure actuelle ({now}). Impossible de déterminer l'état de la marée.")

# ------------------------------------------------
# GESTION DES POMPES / HEURE de marée et Niv EAU
# ------------------------------------------------
def controler_pompes_niveau(bassin_id, distance):

    print(f"Bassin : {bassin_id} / distance : {distance} ")
    
    message = []
    # On récupérer la marée ( montante / descendante )
    type_maree = getMaree()
    print(f"typeMaree = {type_maree}")

    # Check temperature citerne VS tempertaure source
    Source_Temp = data_capteurs.get("Source", {}).get("WaterTemp")
    Citerne_Temp = data_capteurs.get("Citerne", {}).get("WaterTemp")

    # if Citerne_Temp >= (Source_Temp + 2.5):
    #     print("on peut remplir le test, la température est supérieur de 2,5°C ")
    # else:
    #     print(f"On ne peut pas remplir test, température Citerne {Citerne_Temp} VS Source {Source_Temp}")

    # Appliquer les actions de contrôle en fonction du type de marée
    if type_maree == "PM": # and (Citerne_Temp >= (Source_Temp + 2.5)):  # Marée montante
        # On remplit les 2 bassins REF et TEST jusqu'au niveau max de chaque bassin
        for bassin in config_pilotOTT["bassins"]:
            Hauteur_Sensor = float(bassin["Hauteur_Sensor"])
            
            if bassin["ID"] == bassin_id:            
                pompe_remplissage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_REMPLISSAGE"]), None)
                pompe_vidage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_VIDAGE"]), None)
                niveau_actuel = Hauteur_Sensor - distance
                
                # Controle du niveau max... 
                if niveau_actuel >= bassin["NivEau_Max"]:
                    print(f"⚠️ {bassin_id} a atteint son niveau maximal, activation pompe vidage / arrêt pompe remplissage")
                    GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                    GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

                # Control du Niveau minimum 
                elif niveau_actuel <= bassin["NivEau_Min"]:
                    print(f"⚠️ {bassin_id} sous son niveau minimal, activation pompe remplissage / arrêt pompe vidage")
                    GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                    GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 1
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                
                # Control pour arreter de remplir quand le NivEau_Haut est atteind
                elif niveau_actuel >= bassin["NivEau_Haut"]:
                    print(f"🟢 {bassin_id} En marée montante, niveau haut atteind, arret pompe vidage / arret pompe remplissage")
                    GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                    GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0

                # Conditition de remplissage jusqu'au niveau max... 
                else:
                    print(f"🟢 {bassin_id} En marée montante, activation pompe remplissage / arret pompe vidage")
                    GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                    GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 1
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0

                
    elif type_maree == "BM":  # Marée descendante
        for bassin in config_pilotOTT["bassins"]:
            if bassin["ID"] == bassin_id:
                pompe_remplissage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_REMPLISSAGE"]), None)
                pompe_vidage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_VIDAGE"]), None)
                nivEau_Max = float(bassin["NivEau_Max"])
                nivEau_Min = float(bassin["NivEau_Min"])
                nivEau_Bas = float(bassin["NivEau_Bas"])
                Hauteur_Sensor = float(bassin["Hauteur_Sensor"])
                niveau_actuel = Hauteur_Sensor - distance

                if niveau_actuel >= nivEau_Max:
                    print(f"⚠️ {bassin_id} a atteint son niveau maximal, activation pompe  vidage / arret pompe remplissage")
                    GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                    GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

                elif niveau_actuel <= nivEau_Min:
                    print(f"⚠️ {bassin_id} sous son niveau minimal, arrêt pompe vidage / activation pompe remplissage")
                    GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                    GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 1
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                
                elif niveau_actuel < nivEau_Bas:
                    print(f"🟢 {bassin_id} En marée descendante, niveau bas atteind, arret pompe vidage / arret pompe remplissage")

                    GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Activation
                    GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0

                else:
                    print(f"🟢 {bassin_id} En marée descendante, activation pompe vidage / arret pompe remplissage")
                    GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                    GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                    etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                    etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

    # Publier l'état des pompes
    envoyer_etat_pompes()

def envoyer_etat_pompes():
    """Envoie un message MQTT avec l'état actuel de toutes les pompes."""
    global etat_pompes_local

    message = [{"ID": pompe_id, "pump_State": etat} for pompe_id, etat in etat_pompes_local.items()]
    print(f"Envoi etat pompe : {message}")
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    
    print(f"📡 Envoi état global des pompes : {json_message}")

# ------------------
# Connexion MQTT
# ------------------
def on_connect(client, userdata, flags, rc):
    print("📡 Connecté au broker MQTT")
    client.subscribe([(MQTT_ORDERS, 0), (MQTT_DATA, 0)])  # Abonnement aux deux topics

def on_message(client, userdata, msg):
    print(f"📩 Message MQTT reçu sur [{msg.topic}]: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())

        # if msg.topic == MQTT_DATA:
        if msg.topic.startswith("input/data/"):
            id_bassin = payload.get("ID_BASSIN")
            niveau_eau = float(payload.get("Niv_Eau"))
            water_temp = float(payload.get("WaterTemp"))
            air_temp = float(payload.get("AirTemp"))

            # Stockage des dernières valeurs des capteurs 
            data_capteurs[id_bassin] = {
                "Niv_Eau": niveau_eau,
                "WaterTemp": water_temp,
                "AirTemp": air_temp
            }

            print(f"Data Capteur pour {id_bassin} = {data_capteurs[id_bassin]}")
            if id_bassin and niveau_eau is not None:
                controler_pompes_niveau(id_bassin, niveau_eau)

        elif msg.topic == MQTT_ORDERS:
            command = payload.get("order")
            print(f"📩 Commande MQTT reçue : {command} ")

            if command == "remplir":
                controler_pompes("PM")
            elif command == "vider":
                controler_pompes("BM")
            elif command == "stop_ALL":
                print("🔴 Arrêt d'urgence, coupure de toutes les pompes")
                for pompe in config_pilotOTT["pompes"]:
                    GPIO.output(pompe["gpio"], GPIO.LOW)
                    print(f"stop pompe {pompe['gpio']}")
                    client.publish(MQTT_PUMP_STATE, json.dumps({"ID": pompe["ID"], "pump_State": 1}))
                client.publish(MQTT_LOG_GENERAL, json.dumps({"event": "Arrêt d'urgence", "data": "Toutes les pompes arrêtées"}))
            else:
                print(f"Commande inconnue : {command}")

    except json.JSONDecodeError:
        print("Erreur JSON dans le message MQTT")

# -----------------------------
# Communication des states 
# -----------------------------
def envoyer_etat_periodique(delay):
    # """Envoie régulièrement l'état des pompes toutes les X secondes."""
    print("Démarrage Envoi etat périodique")
    while True:
        envoyer_etat_pompes()
        time.sleep(delay)  # Envoi toutes les 60 secondes (modifiable)

# ------------------
# Exécution
# ------------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

try:
    print("🚀 Démarrage du serveur PiloteOTT...")
    config_pilotOTT = charger_configuration()
    # Stockage local des états des pompes pour éviter les actions inutiles
    etat_pompes_local = {}

    # marees = charger_marees()  # Charger les données des marées
    marees_converties = convertir_marees(charger_marees())  # Convertir les marées en objets datetime
    initialiser_pompes()

    # Démarrage du thread d'envoi périodique ( toutes les 60 sec )
    threading.Thread(target=envoyer_etat_periodique,args=(60,), daemon=True).start()
    
    client.loop_forever()
    

except KeyboardInterrupt:
    print("🛑 Arrêt du script.")

finally:
    # GPIO.cleanup()
    print("Stop final")
