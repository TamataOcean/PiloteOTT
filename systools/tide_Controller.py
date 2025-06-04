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

global previous_maree
global nextious_maree
global heating_time
heating_time = datetime.now() - datetime.now()
print(f"heating_time : {heating_time}")

global etat_pompes_local
global etat_chauffages_local

global consignes_citerne		# Variable du statut des consignes de température et niveau d'eau de la Citerne (booléen)   DD, le 19/05/2025
consignes_citerne = 0
#print(f"consignes_citerne : {consignes_citerne}")

data_capteurs = {}
global water_offset
water_offset = 2.5

def charger_configuration():
    try:
        with open(CONFIG_PATH, "r") as fichier:
            print("[CONFIG] - Fichier de configuration trouvé")
            return json.load(fichier)["conf"]
    except Exception as e:
        print(f"[CONFIG] - Erreur lors du chargement du fichier de config : {e}")
        return None

# Charger les données des marées
def charger_marees():
    try:
        with open(MAREES_PATH, "r") as fichier_marees:
            print("[CONFIG] - Fichier des marées trouvé")
            return json.load(fichier_marees)
    except Exception as e:
        print(f"[CONFIG] - Erreur lors du chargement du fichier des marées : {e}")
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
        
        print(f"🔧 INITIALISATION {pompe['ID']} ({pompe['description']}) -> {pompe['etat_initial']}")
        message.append({"ID": pompe["ID"], "pump_State": etat_pompe})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    client.publish(MQTT_LOG_GENERAL, json.dumps({"event": "Etat des pompes au démarrage", "data": message}))

    for chauffage in config_pilotOTT["chauffages"]:
        etat_chauffage = 1 if chauffage['etat_initial'] == "ON" else 0
        etat_chauffages_local[chauffage["ID"]] = etat_chauffage  # Stocker l'état initial localement
        GPIO.setup(chauffage["gpio"], GPIO.OUT)
        GPIO.output(chauffage["gpio"], GPIO.LOW if etat_chauffage else GPIO.HIGH)
        
        print(f"🔧 INITIALISATION {chauffage['ID']} ({chauffage['description']}) -> {chauffage['etat_initial']}")
        message.append({"ID": chauffage["ID"], "pump_State": etat_chauffage})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    client.publish(MQTT_LOG_GENERAL, json.dumps({"event": "Etat des chauffages au démarrage", "data": message}))

# ------------------------------------------
# Extinction de tous les relais()
# ------------------------------------------
def extinction_relais():
    print("[CLOSING] - Arret de tous les relais")
    liste_gpio = [5,6,13,16,19,20,21,26]
    for i in liste_gpio:
        GPIO.setup(i, GPIO.OUT)
        GPIO.output(i, GPIO.HIGH)
        GPIO.setup(i, GPIO.IN)
        time.sleep(0.5)

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
    global previous_maree
    global nextious_maree
    prev_maree = None
    next_maree = None

    for i in range(1, len(marees_converties)):
        if marees_converties[i]["datetime"] > now:
            next_maree = marees_converties[i]
            prev_maree = marees_converties[i - 1]
            nextious_maree = marees_converties[i]["datetime"]
            previous_maree = marees_converties[i - 1]["datetime"]
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
    Source_Temp = data_capteurs.get("Bassin_Source", {}).get("WaterTemp")
    #Source_Temp = 21.25
    if Source_Temp is None:
        Source_Temp = 0
    print(f"Source_Temp : {Source_Temp}")

    Citerne_Temp = data_capteurs.get("Citerne", {}).get("WaterTemp")
    if Citerne_Temp is None:
        Citerne_Temp = 0
    print(f"Citerne_Temp : {Citerne_Temp}")

    Citerne_Distance = data_capteurs.get("Citerne", {}).get("Niv_Eau")
    if Citerne_Distance is None:
        Citerne_Distance = 0
    print(f"Citerne_Distance : {Citerne_Distance}")

    #Citerne_Distance = data_capteurs.get("Citerne", {}).get("Niv-Eau")
    #Citerne_Distance = 500          ######     !!!!!!!!!!!!!!
    #water_offset = config_pilotOTT["temperatures"][0]["WaterTemp_Offset"]            # offset de température de l'eau dû au réchauffement climatique
    global heating_time
    global consignes_citerne
    print(f"consignes_citerne : {consignes_citerne}")
    #global water_offset
    print(f"water_offset : {water_offset}")

    for citerne in config_pilotOTT["citerne"]:
        nivEau_Max_Citerne = float(citerne["NivEau_Max"])
        nivEau_Chauff = float(citerne["NivEau_Chauff"])
        nivEau_Min_Citerne = float(citerne["NivEau_Min"])
        Hauteur_Sensor = float(citerne["Hauteur_Sensor"])

        pompe_remplissage_citerne = next((p for p in config_pilotOTT["pompes"] if p["ID"] == citerne["ID_POMPE_REMPLISSAGE"]), None) 
        chauffage_citerne = next((q for q in config_pilotOTT["chauffages"] if q["ID"] == citerne["ID_CHAUFFAGE"]), None) 
        print(f"GPIO chauffage Citerne : {GPIO.input(20)}")
        #print(f"chauffage_citerne : {chauffage_citerne}")

    nivCiterne = Hauteur_Sensor - Citerne_Distance
    print(f"nivCiterne = {nivCiterne}")

    # Appliquer les actions de contrôle en fonction du type de marée
    if type_maree == "PM" :  # Marée montante
        #print(f"consignes_citerne : {consignes_citerne}")
        if (consignes_citerne == 0):     	# Consigne T° et consigne niveau pas encore atteintes dans la citerne
            #print(f"consignes_citerne : {consignes_citerne}")

            # for citerne in config_pilotOTT["citerne"]:
            #     nivEau_Max_Citerne = float(citerne["NivEau_Max"])
            #     nivEau_Chauff = float(citerne["NivEau_Chauff"])
            #     Hauteur_Sensor = float(citerne["Hauteur_Sensor"])
            #     pompe_remplissage_citerne = next((p for p in config_pilotOTT["pompes"] if p["ID"] == citerne["ID_POMPE_REMPLISSAGE"]), None) 
            #     chauffage_citerne = next((q for q in config_pilotOTT["chauffages"] if q["ID"] == citerne["ID_CHAUFFAGE"]), None) 
            #     print(f"chauffage_citerne : {chauffage_citerne}")

            # Hauteur_Sensor = float(config_pilotOTT["citerne"][0]["Hauteur_Sensor"])
            if nivCiterne >= float(citerne["NivEau_Max"]) :
                print(f"nivCiterne >= NivEau_Max")
                GPIO.output(pompe_remplissage_citerne["gpio"], GPIO.HIGH)  		# Stop pompe remplissage Citerne
                if Citerne_Temp < Source_Temp + water_offset :
                    GPIO.output(chauffage_citerne["gpio"], GPIO.LOW)  	# Activation chauffage Citerne
                elif Citerne_Temp >= Source_Temp  + water_offset :
                    GPIO.output(chauffage_citerne["gpio"], GPIO.HIGH)  	# Stop chauffage Citerne
                    consignes_citerne = 1					# Témoin temp et niveau atteint dans Citerne, OK
                    now = datetime.now()                    # Calcul du temps de chauffe et de remplissage de la citerne depuis la dernière marée 
                    global previous_maree
                    heating_time = now - previous_maree
                    print(f"heating_time : {heating_time}") # heating_time sera rajouté à l'heure de la marée BM suivante pour respecter une durée équivalente PM et BM

            elif nivCiterne >= float(citerne["NivEau_Chauff"]) :
                print(f"nivCiterne >= NivEau_Chauff")
                GPIO.output(pompe_remplissage_citerne["gpio"], GPIO.LOW)  		# Activation pompe remplissage Citerne
                if Citerne_Temp < Source_Temp + water_offset :
                    GPIO.output(chauffage_citerne["gpio"], GPIO.LOW)  	# Activation chauffage Citerne
                elif Citerne_Temp >= Source_Temp  + water_offset :
                    GPIO.output(chauffage_citerne["gpio"], GPIO.HIGH)  	# Stop chauffage Citerne
                
            elif nivCiterne < float(citerne["NivEau_Chauff"]) :
                print(f"nivCiterne < NivEau_Chauff")
                GPIO.output(pompe_remplissage_citerne["gpio"], GPIO.LOW)  		# Activation pompe remplissage Citerne
                GPIO.output(chauffage_citerne["gpio"], GPIO.HIGH)  			# Stop chauffage Citerne

        else:               # Consigne T° et consigne niveau atteintes dans citerne
            GPIO.output(chauffage_citerne["gpio"], GPIO.HIGH)	  # Stop chauffage Citerne

            # On remplit les 2 bassins REF et TEST jusqu'au niveau max de chaque bassin
            for bassin in config_pilotOTT["bassins"]:
                Hauteur_Sensor = float(bassin["Hauteur_Sensor"])
                
                if bassin["ID"] == bassin_id:            
                    pompe_remplissage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_REMPLISSAGE"]), None)
                    pompe_vidage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_VIDAGE"]), None)
                    niveau_actuel = Hauteur_Sensor - distance
                    print(f"niveau {bassin_id} : {niveau_actuel}")
                    
                    # Controle du niveau max... 
                    if niveau_actuel >= bassin["NivEau_Max"]:
                        print(f"⚠️ {bassin_id} a atteint son niveau maximal, activation pompe vidage / arrêt pompe remplissage")
                        GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                        GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                        etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                        etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

                    # Control du Niveau minimum pour le bassin test
                    elif niveau_actuel <= bassin["NivEau_Min"]:
                        print(f"⚠️ {bassin_id} sous son niveau minimal, activation pompe remplissage / arrêt pompe vidage")
                        if bassin["ID"] == "Bassin_Test":
                            if nivCiterne > nivEau_Min_Citerne: 
                                print(f"Le niveau dans la citerne est suffisant, on remplit le bassin de test ")
                                GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                                GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                                etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 1
                                etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                            else # On doit absolument couper la pompe de remplissage du bassin test
                                print(f"Le niveau dans la citerne est insuffisant, on arretela pompe de remplissage du bassin de test ")
                                GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                                GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                                etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                                etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                        
                        if bassin["ID"] == "Bassin_Reference":
                            print(f"On remplit le bassin de référence ")
                            GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                            GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                            etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 1
                            etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                    
                    # Control pour arreter de remplir quand le NivEau_Haut est atteind
                    elif niveau_actuel >= bassin["NivEau_Haut"]:
                        print(f"🟢 {bassin_id} En marée montante, niveau haut atteind, arret pompe vidage / arret pompe remplissage")
                        GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Activation
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

                
    elif type_maree == "BM":  # Marée descendante Basse Mer
        consignes_citerne = 0          # remise à zéro du témoin des consignes dans la citerne
        
        print(f"heating_time : {heating_time}")
        #global nextious_maree
        if (datetime.now() > previous_maree + heating_time):            # Décalage du début de la marée BM de la valeur du temps de chauffe de la citerne à la marée précédente
            print(f"[PROCESS_BM] : Vidange des bassins ")
            for bassin in config_pilotOTT["bassins"]:
                if bassin["ID"] == bassin_id:
                    pompe_remplissage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_REMPLISSAGE"]), None)
                    pompe_vidage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_VIDAGE"]), None)
                    nivEau_Max = float(bassin["NivEau_Max"])
                    nivEau_Min = float(bassin["NivEau_Min"])
                    nivEau_Bas = float(bassin["NivEau_Bas"])
                    Hauteur_Sensor = float(bassin["Hauteur_Sensor"])
                    niveau_actuel = Hauteur_Sensor - distance
                    print(f"niveau_actuel = {niveau_actuel}")
                    if niveau_actuel >= 0 : 

                        if niveau_actuel >= nivEau_Max:
                            print(f"⚠️ {bassin_id} a atteint son niveau maximal, activation pompe  vidage / arret pompe remplissage")
                            GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                            GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                            etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                            etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

                        elif niveau_actuel <= nivEau_Min:
                            #print(f"⚠️ {bassin_id} sous son niveau minimal, arrêt pompe vidage / activation pompe remplissage")
                            print(f"⚠️ {bassin_id} sous son niveau minimal, arrêt pompe vidage / VERIFIER NIVEAU !!")
                            GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                            #GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation
                            GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                            etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                            etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0
                        
                        elif niveau_actuel < nivEau_Bas:
                            print(f"🟢 {bassin_id} En marée descendante, niveau bas atteind, arret pompe vidage / arret pompe remplissage")
                            GPIO.output(pompe_vidage["gpio"], GPIO.HIGH)  # Désactivation
                            GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                            etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                            etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 0

                        elif niveau_actuel < nivEau_Max :
                            print(f"🟢 {bassin_id} En marée descendante, activation pompe vidage / arret pompe remplissage")
                            GPIO.output(pompe_vidage["gpio"], GPIO.LOW)  # Activation
                            GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation
                            etat_pompes_local[bassin["ID_POMPE_REMPLISSAGE"]] = 0
                            etat_pompes_local[bassin["ID_POMPE_VIDAGE"]] = 1

                        else :
                            print(f"Niveau actuel indéterminé ???? ")    
                    else :
                        print(f"Niveau actuel négatif !!!!!!! Probleme de mesure !!")

    # Publier l'état des pompes
    envoyer_etat_pompes()

def envoyer_etat_pompes():
    """Envoie un message MQTT avec l'état actuel de toutes les pompes."""
    global etat_pompes_local
    global etat_chauffages_local

    message = [{"ID": pompe_id, "pump_State": etat} for pompe_id, etat in etat_pompes_local.items()]
    print(f"Envoi etat pompe : {message}")
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    
    #print(f"📡 Envoi état global des pompes : {json_message}")

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
                    # GPIO.output(pompe["gpio"], GPIO.LOW)
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
    etat_chauffages_local = {}

    # marees = charger_marees()  # Charger les données des marées
    marees_converties = convertir_marees(charger_marees())  # Convertir les marées en objets datetime
    initialiser_pompes()

    # Démarrage du thread d'envoi périodique ( toutes les 60 sec )
    etatPerio_thread = threading.Thread(target=envoyer_etat_periodique,args=(60,), daemon=True)
    etatPerio_thread.start()
    
    client.loop_forever()
    

except KeyboardInterrupt:
    print("🛑 Arrêt du script.")
        

finally:
    extinction_relais()
    GPIO.cleanup()
    #etatPerio_thread.join()
    print("Stop final")
 
