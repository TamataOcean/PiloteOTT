# PiloteOTT
Dispositif permettant de comparer l'évolution du biofilm sur l'estran dans des conditions de réchauffement climatique à 2,5°C.

![image](https://github.com/user-attachments/assets/e6b59961-13de-41b3-9608-c83b2e5d2e04)

# Installation

### Node-RED Install / Config
    bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered)
    sudo systemctl enable nodered.service
#### Composant Ui 
    npm install node-red-dashboard
### InfluxDB component - https://flows.nodered.org/node/node-red-contrib-influxdb
    npm install node-red-contrib-influxdb

### Installer Mosquitto
    sudo apt install -y mosquitto

### Installation python & dépendances
    sudo apt-get -y install python3-pip
    sudo pip3 install paho-mqtt --break-system-packages

##### Ajout du service python tide_Controller.py
    sudo cp ~/code/PiloteOTT/deploy/piloteOTT.service.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable piloteOTT.service.service
    sudo systemctl start piloteOTT.service.service