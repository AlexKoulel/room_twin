#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_BME280.h>
#include "config.h"

const char *id = DEVICE_ID;

char topicData[64], topicStatus[64], topicCmd[64];
char clientId[32];

unsigned long interval = DEFAULT_INTERVAL;
unsigned long lastPublish = 0;
bool sensorOk = true;

Adafruit_BME280 bme; 
WiFiClient wifiClient;
PubSubClient client(wifiClient);

void setup() {
  Serial.begin(115200);
  while(!Serial);

  if(!bme.begin(0x76) && !bme.begin(0x77)) {
    Serial.println("Could not connect to the BME280 sensor. Check wiring.\n");
    while (1) delay(1000);
  }

  if(strlen(id) == 0 || strlen(id) > 20 || strpbrk(id,"/+#")) {
    Serial.println("Device id in config.h is not valid\n");
    while (1) delay(1000);
  }

  buildTopics();
  client.setServer(MQTT_HOST, MQTT_PORT);
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
    publishValues();
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
    Serial.printf("Interval is too low, lowest possible value is %d ms\n", MIN_INTERVAL);
    v = MIN_INTERVAL;
  } 
  else if (v > MAX_INTERVAL){
    Serial.printf("Interval is too high, highest possible value is %d ms\n", MAX_INTERVAL);
    v = MAX_INTERVAL;
  } 
  interval = (unsigned long)v;
  Serial.printf("Interval is now %lu ms\n", interval);
}

void connectToWifi(){
  Serial.println("Connecting to WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID,WIFI_PASS);
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
      client.publish(topicStatus, sensorOk ? "online" : "sensor_error", true);
      client.subscribe(topicCmd,1);
      lastPublish = millis() - interval;
    }
    else {
      Serial.printf("Something went wrong, try again in 5 seconds.\n");
      delay(5000);
    }
  }
}

void publishValues() {
  float temp = bme.readTemperature();
  float pres = bme.readPressure()/ 100.0F;
  float humi = bme.readHumidity();


  if(isnan(temp) || isnan(pres) || isnan(humi))
  {
    if(sensorOk) 
    {
      client.publish(topicStatus, "sensor_error",true);
      sensorOk = false;
    }
    Serial.println("BME280 sensor failed.");
    return;
  }
  if(!sensorOk) {
    client.publish(topicStatus, "online",true);
    sensorOk = true;
  }
  char values[96];
  snprintf(values, sizeof(values), "{\"Temperature\": %.2f, \"Humidity\": %.2f, \"Pressure\": %.2f}", temp, humi, pres);
  client.publish(topicData,values);
  Serial.println(values);
}
