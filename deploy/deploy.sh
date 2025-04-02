# Node-RED Install / Config
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

echo "######### Installation Mosquitto"
sudo apt install -y mosquitto

echo "######### Installation python & dépendances"
sudo apt-get -y install python3-pip
sudo pip3 install paho-mqtt --break-system-packages

# Ajout du service python tide_Controller.py
sudo cp ~/code/PiloteOTT/deploy/piloteOTT.service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable piloteOTT.service.service
sudo systemctl start piloteOTT.service.service