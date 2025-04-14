# -----------
### NODE JS
# -----------
sudo apt install -y ca-certificates curl gnupg
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/nodesource.gpg
NODE_MAJOR=20
echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt update
sudo apt install -y nodejs

# -----------
### INFLUXDB
# -----------
sudo apt update
sudo apt install -y gnupg2 curl wget
wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
echo "deb https://repos.influxdata.com/debian bulleye stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

sudo apt update
sudo apt install -y influxdb

# -----------
### NODE-RED
# -----------
# Process > https://nodered.org/docs/getting-started/raspberrypi
cd
echo "######### Installation Node-Red"
bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered)
echo "Adding Node-Red as a service"
sudo systemctl enable nodered.service
# Composant Ui 
npm install node-red-dashboard
# InfluxDB component - https://flows.nodered.org/node/node-red-contrib-influxdb
npm install node-red-contrib-influxdb

# -----------
### MOSQUITTO
# -----------
echo "######### Installation Mosquitto"
sudo apt install -y mosquitto

# -----------
### PYTHON
# -----------
echo "######### Installation python & dépendances"
sudo apt-get -y install python3-pip
sudo pip3 install paho-mqtt --break-system-packages

# Ajout du service python tide_Controller.py
sudo cp ~/code/PiloteOTT/deploy/piloteOTT.service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable piloteOTT.service.service
sudo systemctl start piloteOTT.service.service

# INSTALL DU RELAY 
# Procédure : https://www.waveshare.com/wiki/RPi_Relay_Board_(B)#Others
