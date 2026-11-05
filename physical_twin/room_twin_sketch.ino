#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_BME280.h>

const char *id = "1";
const char *ssid = "CHANGE_TO_YOUR_NETWORK";        
const char *password = "CHANGE_TO_YOUR_PASSWORD";  
const int port = 0; 

const long DEFAULT_INTERVAL = 5000;
const long MIN_INTERVAL = 1000;
const long MAX_INTERVAL = 8000;

char topicData[64], topicStatus[64], topicCmd[64];
char clientId[32];

unsigned long interval = DEFAULT_INTERVAL;
unsigned long lastPublish = 0;

Adafruit_BME280 bme; 
WiFiClient wifiClient;
PubSubClient client(wifiClient);
IPAddress server(0,0,0,0); //Change



void setup() {
  Serial.begin(115200);
  while(!Serial);

  if(!bme.begin(0x76) && !bme.begin(0x77)) {
    Serial.println("Could not connect to the BME280 sensor. Check wiring.");
    while (1) delay(10);
  }
  buildTopics();
  client.setServer(server, port);
  client.setCallback(onCommand);
  connectToWifi();
}

void loop() {
  if(WiFi.status() != WL_CONNECTED){
    connectToWifi();
  }
  if(!client.connected()) {
    connectMqtt();
  }

  client.loop();

  unsigned long now = millis();
  if(now - lastPublish >= interval) {
    lastPublish = now;
    printValues();
  }
}

void buildTopics() {
  snprintf(topicData,sizeof(topicData),"dt/room_twin/%s/telemetry",id); 
  snprintf(topicStatus,sizeof(topicStatus),"dt/room_twin/%s/status",id);
  snprintf(topicCmd,sizeof(topicCmd),"dt/room_twin/%s/cmd",id);
  snprintf(clientId,sizeof(clientId),"room_twin-%s",id);
}

void onCommand(char *topic, byte *payload, unsigned int length) {
  char buf[96];
  unsigned int n = length < sizeof(buf) - 1 ? length : sizeof(buf) - 1;
  memcpy(buf, payload, n);
  buf[n] = '\0';

  const char *p = strstr(buf, "interval_ms");
  if (!p) return;
  p = strchr(p, ':');
  if (!p) return;

  long v = atol(p + 1);
  if (v < MIN_INTERVAL) {
    Serial.printf("Interval is too low, lowest possible value is 1000ms\n");
    v = MIN_INTERVAL;
  } 
  else if (v > MAX_INTERVAL){
    Serial.printf("Interval is too high, highest possible value is 8000ms\n");
    v = MAX_INTERVAL;
  } 
  interval = (unsigned long)v;
  Serial.printf("Interval is now %lu ms\n", interval);
}

void connectToWifi(){
  Serial.println("Connecting to WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid,password);
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi connected");
}

void connectMqtt() {
  while(!client.connected()) {
    if (WiFi.status() != WL_CONNECTED) return;
    Serial.print("Attempting MQTT connection...");
    if(client.connect(clientId,NULL,NULL,topicStatus,1,true,"offline")) {
      Serial.println("MQTT connected.");
      client.publish(topicStatus, "online", true);
      client.subscribe(topicCmd,1);
      lastPublish = millis() - interval;
    }
    else {
      Serial.printf("Something went wrong, try again in 5 seconds.");
      delay(5000);
    }
  }
}

void printValues() {
  float temp = bme.readTemperature();
  float pres = bme.readPressure()/ 100.0F;
  float humi = bme.readHumidity();

  char values[96];
  snprintf(values, sizeof(values), "{\"Temperature\": %.2f, \"Humidity\": %.2f, \"Pressure\": %.2f}", temp, humi, pres);
  client.publish(topicData,values);
  Serial.println(values);
}
