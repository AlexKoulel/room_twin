import argparse
import os
import json
import yaml
import paho.mqtt.client as mqtt
import math
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
from pathlib import Path

from functions import load_json, load_yaml, sensor_point, anomaly_point
from twin import Twin

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config.yaml")
args = ap.parse_args()

CONNECTIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "connections.json"
)
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    args.config
)

connections = load_json(CONNECTIONS_PATH)
config = load_yaml(CONFIG_PATH)

twin = Twin(config)

#connections.json vars
MQTT_BROKER  = connections['RT_MQTT_BROKER']           
MQTT_PORT    = connections['RT_MQTT_PORT']       
TELEMETRY_TOPIC   = connections['RT_TELEMETRY_TOPIC'].format(twin.device_id)
STATUS_TOPIC = connections['RT_STATUS_TOPIC'].format(twin.device_id)
CMD_TOPIC = connections['RT_CMD_TOPIC'].format(twin.device_id)
ANOMALY_TOPIC = connections['RT_ANOMALY_TOPIC'].format(twin.device_id)
INFLUX_URL    = connections['RT_INFLUX_URL']
INFLUX_TOKEN  = connections['RT_INFLUX_TOKEN']  
INFLUX_ORG    = connections['RT_INFLUX_ORG'] 
INFLUX_BUCKET = connections['RT_INFLUX_BUCKET']  

influx_client = InfluxDBClient(
    url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=2000)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc, properties):
    if rc.is_failure:
        print(f"Failed to connect: {rc}")
        return
    print("Connected to MQTT broker\n")
    for key, (lo, hi) in twin.limits.items():
        print(f"{key} limits: min {lo}, max {hi}")
    print(f"Intervals: normal {twin.normal_interval} ms, fast {twin.fast_interval} ms\n")
    print(f"Interval is set at {twin.normal_interval}.\n")
    client.subscribe(STATUS_TOPIC)
    client.subscribe(TELEMETRY_TOPIC)

def save_to_db(point):
    try:
        write_api.write(bucket=INFLUX_BUCKET, record=point)
    except Exception as e:
        print(f"[DB] Saving failed: {e}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        if msg.topic == STATUS_TOPIC:
            print(f"Device {twin.device_id} is {payload}")
            if payload == "online":
                twin.device_online()  
            if payload == "sensor_error":
                report_anomaly(client, "BME280 sensor failed.")
            return
        
        data = json.loads(payload)
        
        now = time.time()
        prediction = None
        if twin.last_time == None:
            print("Predicions will start from the next measurement.")
        else:
            prediction = twin.predict(now - twin.last_time) 
        twin.last_time = now

        anomalies = twin.find_anomalies(data)
        for reason in anomalies:
                report_anomaly(client, reason)
        if any("invalid" in a for a in anomalies): 
            return
        
        if prediction is not None:
            residual = data["Temperature"] - prediction
            data.update({'TPrediction':prediction, 'Residual': residual })
            reason = twin.check_residual(residual)
            if reason is not None:
                report_anomaly(client,reason)

        violations, new_interval = twin.check_thresholds(data)
        
        if new_interval is not None:
            client.publish(CMD_TOPIC, json.dumps({"interval_ms": new_interval}),qos=1)
            for v in violations:
                print(f"[WRN] Device - {twin.device_id}: {v}.")
            print(f"[CMD] Changed interval to {new_interval}.\n")

        save_to_db(sensor_point(twin.device_id, data))

        print("\n")
        print(f"Device {twin.device_id} - {twin.device_location}")
        print("==================================")
        print("Saving measurements to database:")
        print(f"Temperature: {data['Temperature']} °C")
        print(f"Humidity: {data['Humidity']} %")
        print(f"Pressure: {data['Pressure']} hPa")
        print("==================================\n")
        if prediction is not None:
            print(f"Prediction: {prediction: .2f} °C, residual: {residual:+.2f} °C")
    except Exception as e:
        print(f"Error: {e}")
    

def report_anomaly(client, reason):
    print(f"[ANOMALY] {twin.device_id}: {reason}")
    client.publish(ANOMALY_TOPIC, json.dumps({"device": twin.device_id, "reason": reason}), qos=1)
    save_to_db(anomaly_point(twin.device_id, reason))
        
def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    print("\nConnecting to MQTT broker...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
