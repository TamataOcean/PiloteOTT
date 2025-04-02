# import RPi.GPIO as GPIO
import time
import requests
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# Configuration MQTT
MQTT_BROKER =       "localhost"
MQTT_PUMP_STATE =   "server/pumpState"
MQTT_LOG_GENERAL =  "server/log"
MQTT_DATA =         "input/data"
MQTT_ORDERS =       "input/orders"
MQTT_PORT =         1883

# Chargement du fichier de configuration
CONFIG_PATH = "/home/bibi/code/pilotOTT/config/config_PilotOTT.json"

def charger_configuration():
    try:
        with open(CONFIG_PATH, "r") as fichier:
            return json.load(fichier)["conf"]
    except Exception as e:
        print(f"Erreur lors du chargement du fichier de config : {e}")
        return None

# Initialisation des GPIO
def initialiser_pompes():
    message = []
    for pompe in config_pilotOTT["pompes"]:
        etat_pompe = 1 if pompe['etat_initial'] == "ON" else 0
        # GPIO.output(pompe["gpio"], GPIO.LOW if etat_pompe else GPIO.HIGH)
        print(f"🔧 Initialisation {pompe['ID']} ({pompe['description']}) -> {pompe['etat_initial']}")
        message.append({"ID": pompe["ID"], "pump_State": etat_pompe})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)
    client.publish(MQTT_LOG_GENERAL, json.dumps({"event": "Etat des pompes au démarrage", "data": message}))

# Contrôle des pompes en fonction des marées
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
        # GPIO.output(pompe["gpio"], GPIO.LOW if etat_pompe else GPIO.HIGH)
        print(f"🔧 {pompe['ID']} -> {'ON' if etat_pompe else 'OFF'}")
        message.append({"ID": pompe["ID"], "pump_State": etat_pompe})
    
    json_message = json.dumps(message)
    client.publish(MQTT_PUMP_STATE, json_message)

# Contrôle des pompes en fonction des niveaux d'eau
def controler_pompes_niveau(bassin_id, niveau_actuel):
    message = []

    for bassin in config_pilotOTT["bassins"]:
        if bassin["ID"] == bassin_id:
            
            pompe_remplissage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_REMPLISSAGE"]), None)
            pompe_vidage = next((p for p in config_pilotOTT["pompes"] if p["ID"] == bassin["ID_POMPE_VIDAGE"]), None)
            print(f"Pompe Remplissage pour le {bassin["ID"]} : {pompe_remplissage["ID"]} ")            
            print(f"Pompe Vidage pour le le {bassin["ID"]} : {pompe_vidage["ID"]} ")

            if niveau_actuel >= bassin["NivEau_Max"]:
                print(f"⚠️ {bassin_id} a atteint son niveau maximal, arrêt de la pompe de remplissage")
                # GPIO.output(pompe_remplissage["gpio"], GPIO.HIGH)  # Désactivation

                message.append({"ID": bassin["ID_POMPE_REMPLISSAGE"], "pump_State": 0})
                client.publish(MQTT_PUMP_STATE, json.dumps(message))
                print(f"🔴 Pompe {bassin['ID_POMPE_REMPLISSAGE']} arrêtée")
            elif niveau_actuel <= bassin["NivEau_Min"]:
                print(f"🟢 {bassin_id} sous son niveau minimal, activation de la pompe de remplissage")
                # GPIO.output(pompe_remplissage["gpio"], GPIO.LOW)  # Activation

                message.append({"ID": bassin["ID_POMPE_REMPLISSAGE"], "pump_State": 1})
                client.publish(MQTT_PUMP_STATE, json.dumps(message))
                print(f"🟢 Pompe {bassin['ID_POMPE_REMPLISSAGE']} activée")


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

        if msg.topic == MQTT_DATA:
            id_bassin = payload.get("ID_BASSIN")
            niveau_eau = payload.get("Niv_Eau")
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

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

try:
    print("🚀 Démarrage du serveur PiloteOTT...")
    config_pilotOTT = charger_configuration()
    initialiser_pompes()
    client.loop_forever()

except KeyboardInterrupt:
    print("🛑 Arrêt du script.")

finally:
    # GPIO.cleanup()
    print("Stop final")
