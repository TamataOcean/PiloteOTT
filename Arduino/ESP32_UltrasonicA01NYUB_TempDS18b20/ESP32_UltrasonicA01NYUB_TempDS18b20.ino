/*
**********************************************************************  
****  Pilote-OTT Project : Water level and Temperatures Sensor    ****
**********************************************************************
*
* Hardware :
* - ESP32 Wroom Wifi board
* - DFROBOT A01NYUB Waterproof Ultrasonic Sensor 
* - DALLAS DS18b20 Digital Temperature sensor
*
* author  :  Rominco(rtourte@yahoo.fr) and Denis DAUSSE (CNRS)
* version :  V1.0
* date    :  2025-03-18
* 
**********************************************************************
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <HardwareSerial.h>

//#include "Adafruit_CCS811.h"
//#include "SparkFunBME280.h"

// DS18B20 Library
#include <OneWire.h> 
#include <DallasTemperature.h>

// Define Wiring on ESP32
#define RXD2 16   // Receive pin for UART2 on ESP32, wired with Ultrasonic Sensor TX pin
#define TXD2 17   // Transmitt pin for UART2 on ESP32, wired with Ultrasonic Sensor RX pin
#define ONE_WIRE_BUS 14   // One-Wire data bus pin

HardwareSerial SerialPort(2);  // use UART2 with the name SerialPort
OneWire oneWire(ONE_WIRE_BUS);

// variable to hold DS18b20 device addresses
DeviceAddress Thermometer;
DallasTemperature sensorDS18B20(&oneWire);
int deviceCount = 0;

int basin_number = 3;    //############ HERE, CHOOSE THE BASIN NUMBER (1 or 2 or 3 or ...)   #############

// ****   NETWORK setup    ****
const char* ssid     = "WifiRaspi";   //"WifiRaspi"
const char* password = "wifiraspi";         //"wifiraspi"

//const char* mqtt_server = "192.168.1.105"; //"172.24.1.1"
const char* mqtt_server = "172.24.1.93"; // Passerelle par defaut du raspi

//const char* mqtt_output = "esp32/update";
const char* mqtt_output = "input/data/Bassin_Test";
const char* mqtt_input = "esp32/input";
const char* mqtt_log = "esp32/log";
const char* mqtt_user = "Groupe_74";    //"ESP32_Proto_Exemple"
const char* mqtt_password = "password";
const char mqtt_UUID[] = "UNIV_PUT_YOUR_UNIQUE_NAME";
const char* ID_BASSIN = "Bassin_Test";

const int ledPin = 4;
int timeInterval = 2000;      //7500

float WaterTemp = 0;
float AirTemp = 0;
int NivEau = 0;

WiFiClient espClient;
PubSubClient client(espClient);
long lastMsg = 0;
char msg[50];
int value = 0;

/* ------------------------
 *  MAIN SETUP 
 *  -----------------------
 */
void setup()
{
    Serial.begin(115200);
    delay(10);
    SerialPort.begin(9600, SERIAL_8N1, RXD2, TXD2);   // for Ultrasonic distancemeter
  
    setup_wifi();
    client.setServer(mqtt_server, 1883);
    client.setCallback(callback);

    /*  DS18B20 Sensor          */
    Serial.println("DS18B20 Dallas Temperature begin"); 
    sensorDS18B20.begin(); 
    // locate devices on the bus
    Serial.println("Locating devices...");
    Serial.print("Found ");
    deviceCount = sensorDS18B20.getDeviceCount();   // counting number of devices on the bus
    Serial.print(deviceCount, DEC);
    Serial.println(" DS18b20 devices.");
    Serial.println("");
    sensorDS18B20.setResolution(12);      // set all DS18b20 plugged on the bus to 12 bits resolution
    Serial.println("Printing addresses and getting 12 bits resolution...");
    for (int i = 0;  i < deviceCount;  i++)
    {
      Serial.print("Sensor ");
      Serial.print(i+1);
      Serial.print(" : ");
      sensorDS18B20.getAddress(Thermometer, i);   // get each DS18b20 64bits address
      printAddress(Thermometer);            // function at the end of this code
      //Serial.print(Thermometer);
      Serial.print("resolution is ");
      Serial.print(sensorDS18B20.getResolution(Thermometer));
      Serial.println(" bits");
    }
}       // setup end 

/* 
 *  ------------------
 *  MAIN LOOP
 *  ------------------
 */
void loop() {

//  int distance = 99999;
//  int high = 0;
//  int low = 0;
//  int checksum = 0;
//  int header = 0;

//  int16_t distance;  
//  bool newData = false; 
//  uint8_t buffer[4];  
//  uint8_t idx = 0;  
  
  long now = millis();
  if (now - lastMsg > timeInterval ) {
    lastMsg = now;
    if (!client.connected()) {
      Serial.println("Reconnect to Mqtt");
      reconnect();
    }
    client.loop();        // ?????????????????????    MQTT PubSub
  
    Serial.print(" Requesting temperatures..."); 
    sensorDS18B20.requestTemperatures();
    Serial.println("DONE"); 
    delay(700);     // DS18b20 Conversion time for 12 bits resolution
    Serial.print(" WaterTemp : ");
    WaterTemp = sensorDS18B20.getTempCByIndex(0);
    Serial.println(WaterTemp, 3);

    Serial.print(" AirTemp: ");
    AirTemp = sensorDS18B20.getTempCByIndex(1);
    Serial.println(AirTemp, 3);
    
    Serial.print(" Niv_Eau : ");
    NivEau = waterlevel();
    //NivEau = -3.14156;
    //SerialPort.flush();
    Serial.print( NivEau);
    Serial.print(" mm");

    //NivEau = distance ;
    //Serial.print(NivEau, 2);
    //Serial.print(NivEau);
    
    Serial.println();
    //JSON phrase : {"ID_BASSIN":"Bassin_Test", "Num_Bassin":1, "Niv_Eau":15.73, "WaterTemp":14.49, "AirTemp":17.87}
    //String json = "{\"user\":\""+(String)mqtt_user+"\",\"Humidity\":\""+(String)sensorBME280.readFloatHumidity()+"\",\"Pressure\":\""+(String)sensorBME280.readFloatPressure()+"\",\"Altitude\":\""+(String)sensorBME280.readFloatAltitudeMeters()+"\",\"AirTemperature\":\""+(String)sensorBME280.readTempC()+"\",\"WaterTemperature_1\":\""+(String)sensorDS18B20.getTempCByIndex(0)+"\",\"WaterTemperature_2\":\""+(String)sensorDS18B20.getTempCByIndex(1)+"\"}";
    //String json = "{\"user\":\""+(String)mqtt_user+"\",\"Humidity\":\""+(String)sensorBME280.readFloatHumidity()+"\",\"Pressure\":\""+(String)sensorBME280.readFloatPressure()+"\",\"Altitude\":\""+(String)sensorBME280.readFloatAltitudeMeters()+"\",\"AirTemperature\":\""+(String)sensorBME280.readTempC()+"\",\"WaterTemperature_1\":\""+(String)sensorDS18B20.getTempCByIndex(0)+"\",\"WaterTemperature_2\":\""+(String)sensorDS18B20.getTempCByIndex(1)+"\"}";

    //String json = "{\"user\":\""+(String)mqtt_user+"\",\"Num_Bassin\":\""+(String)basin_number+"\",\"Niv_Eau\":\""+(String)NivEau+"\",\"WaterTemp\":\""+String(WaterTemp,3)+"\",\"AirTemp\":\""+String(AirTemp,3)+"\"}";
    String json = "{\"user\":\""+(String)mqtt_user+"\",\"ID_BASSIN\":\""+ID_BASSIN+"\",\"Niv_Eau\":\""+(String)NivEau+"\",\"WaterTemp\":\""+String(WaterTemp,3)+"\",\"AirTemp\":\""+String(AirTemp,3)+"\"}";
    client.publish(mqtt_output, json.c_str() );
    client.disconnect();

    Serial.println("Mqtt sent to : " + (String)mqtt_output );
    Serial.println(json);
    delay(100);
  }
}

/* ----------------------
 *  printAddress 
 *  ---------------------
 */
void printAddress(DeviceAddress deviceAddress)
{ 
  for (uint8_t i = 0; i < 8; i++)
  {
    Serial.print("0x");
    if (deviceAddress[i] < 0x10) Serial.print("0");
    Serial.print(deviceAddress[i], HEX);
    if (i < 7) Serial.print(", ");
  }
  Serial.println("");
}

/* ----------------------
 *  WIFI SETUP 
 *  ---------------------
 */
void setup_wifi() {
  delay(10);
  // We start by connecting to a WiFi network
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

/* 
 *  ------------------
 *  RECONNECT MQTT
 *  ------------------
 */
void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    delay(100);
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    if (client.connect(mqtt_UUID , mqtt_user, mqtt_password )) {
    //if (client.connect("ESP8266Client")) {
      Serial.println("connected");
      // Subscribe
      client.subscribe(mqtt_input);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(3000);
    }
  }
}

/* ------------------------
 *  MQTT CALLBACK
 *  -----------------------
 */
void callback(char* topic, byte* message, unsigned int length) {
  Serial.print("Message arrived on topic: ");
  Serial.print(topic);
  Serial.print(". Message: ");
  String messageTemp;
  
  for (int i = 0; i < length; i++) {
    Serial.print((char)message[i]);
    messageTemp += (char)message[i];
  }
  Serial.println();

  // Feel free to add more if statements to control more GPIOs with MQTT

  // If a message is received on the topic esp32/input, you check if the message is either "on" or "off". 
  // Changes the output state according to the message
  if (String(topic) == mqtt_input ) {
    Serial.print("Changing output to ");

    if(messageTemp == "on"){
      Serial.println("MessageTemp = on");
      client.publish(mqtt_log, "changing to ON" );
      digitalWrite(ledPin, HIGH);
    }
    else if(messageTemp == "Message Temp = off"){
      Serial.println("off");
      client.publish(mqtt_log, "changing to OFF" );
      digitalWrite(ledPin, LOW);
    }
    else if(messageTemp == "timeInterval_1000") {
      Serial.println("Time Interval order received");
      timeInterval = 1000;
      client.publish(mqtt_log, "Interval set to 1000" );
    }
    else if(messageTemp == "timeInterval_5000") {
      Serial.println("Time Interval order received");
      timeInterval = 5000;
      client.publish(mqtt_log, "Interval set to 5000" );
    }
    else if(messageTemp == "reboot") {
      Serial.println("Reboot order received");
      String msg = "Reboot for : " + (String)mqtt_user;
      client.publish(mqtt_log, msg.c_str() );
      ESP.restart();
    }
  }
}


////int16_t waterlevel() {
//float waterlevel() {
//  //int16_t distance = 0;  
//  float distance = 0;  
//  bool newData = false; 
//  uint8_t buffer[4];  
//  uint8_t idx = 0;  
//  unsigned long interval = 100;
//  unsigned long lastTime = 0 ;
//  unsigned long startTime = millis();
//  
//  SerialPort.flush();
//  while (lastTime < startTime + interval) {
//
//    if (SerialPort.available()) {  
//        uint8_t c = SerialPort.read(); 
//        if (idx == 0 && c == 0xFF) {
//          buffer[idx++] = c;
//        }
//        else if ((idx == 1) || (idx == 2)) {
//          buffer[idx++] = c;
//        }
//        else if (idx == 3) {
//          uint8_t sum = 0;
//          sum = buffer[0] + buffer[1] + buffer[2];
//          if (sum == c) {
//            distance = ((uint16_t)buffer[1] << 8) | buffer[2];
//            newData = true;
//          }
//          idx = 0;
//        }
//      }
//      lastTime = millis();
//      if (newData) {
//          newData = false;
//          break;
//        }
//  }
//  Serial.print("\nDistance (mm): ");
//  Serial.print(distance);
//  Serial.print(" mm");
//  return (distance);
//        
//}
//

/////////////////////////////////////////////////////////// 

//int distance() {
//  int levelheight = 9999; // Variable to store distance in millimeters
//  int measure = -1;
//  unsigned long currentMillis = millis();   //instant present
//  unsigned long timeOut = millis() + 5000 ;   //instant present + 5seconds
//  int high = 0;
//  int low = 0;
//  int checksum = 0;
//  int header = 0;
//  
//  SerialPort.flush();
//
//  if (currentMillis < timeOut)  {
//    // Process data if available
//      if (SerialPort.available()) {
//        header = SerialPort.read();
//        //Serial.println("SerialPort available!");
//  
//        if (header == 0xff) {
//          // Read the next bytes
//          //Serial.println("header is 0xff !");
//          if (SerialPort.available() >= 3) {
//            high = SerialPort.read();
//            low = SerialPort.read();
//            checksum = SerialPort.read();
//  
//            // Compute distance
//            //int measure = ((high << 8) + low);
//            measure = ((high << 8) + low);
//            Serial.print("measure: ");
//            Serial.println(measure);
//  
//           /* // Convert distance to cm
//            mostRecentDistance = distance / 10.0;
//           */
//        // Clear any remaining data in the buffer
//        SerialPort.flush();
//        currentMillis = timeOut;    // time is out, exit loop
//        } 
//      }
//      if ( measure>= 0) {
//        levelheight = measure;
//      }
//      
//      }
//    else {
//      currentMillis = millis();   //instant present
//      }
//  }
//    Serial.print("levelheight: ");
//    Serial.println(levelheight);
//    return (levelheight);
//    //return (measure);
//    
//  //}
//}


 /*  ------------------
 *  Distance measurement with A01NYUB
 *  ------------------
 */
int waterlevel() {
  int new_distance;
  bool newData = false;
  while (true) {
       unsigned char data[4] = {};
       SerialPort.flush();
       do {
            for (int i = 0; i < 4; i++) {
                data[i] = SerialPort.read();
            }
        } while (SerialPort.read() == 0xff);
        
        if (data[0] == 0xff) {
            int sum;
            sum = (data[0] + data[1] + data[2]) & 0x00FF;
            if (sum == data[3]) {
                new_distance = (data[1] << 8) + data[2];
                newData = true;
                //Serial.print("    Marque1");
            } else {
                new_distance = -1;    // error check sum
                //Serial.print("    Marque Error");
                 delay(100);
            }
        }
          if (newData) {
            newData = false;
            break;
          }
    }
  //delay(100);
  return (new_distance);
}
