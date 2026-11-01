import argparse
import os
import json
import yaml
import paho.mqtt.client as mqtt
import math
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
from pathlib import Path

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

with open(CONNECTIONS_PATH, "r") as f:
    connections = json.load(f)
    
with open(CONFIG_PATH, "r") as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)
    
#cofig yaml vars
device_id = str(config["device"]["id"])
device_location = config["device"]["location"]
normal_interval = config["intervals"]["normal_ms"]
fast_interval = config["intervals"]["fast_ms"]

LIMITS = {
    "Temperature": (config["thresholds"]["temperature"]["min"], config["thresholds"]["temperature"]["max"]),
    "Humidity":    (config["thresholds"]["humidity"]["min"],    config["thresholds"]["humidity"]["max"]),
    "Pressure":    (config["thresholds"]["pressure"]["min"],    config["thresholds"]["pressure"]["max"]),
}

max_jump = config["anomaly"]["max_jump"]
frozen_count = config["anomaly"]["frozen_count"]

#connections.json vars
MQTT_BROKER  = connections['RT_MQTT_BROKER']           
MQTT_PORT    = connections['RT_MQTT_PORT']       
TELEMETRY_TOPIC   = connections['RT_TELEMETRY_TOPIC'].format(device_id)
STATUS_TOPIC = connections['RT_STATUS_TOPIC'].format(device_id)
CMD_TOPIC = connections['RT_CMD_TOPIC'].format(device_id)
ANOMALY_TOPIC = connections['RT_ANOMALY_TOPIC'].format(device_id)
INFLUX_URL    = connections['RT_INFLUX_URL']
INFLUX_TOKEN  = connections['RT_INFLUX_TOKEN']  
INFLUX_ORG    = connections['RT_INFLUX_ORG'] 
INFLUX_BUCKET = connections['RT_INFLUX_BUCKET']  

current_interval = {}
last_temp = None
same_count = 0

RANGES = {"Temperature": (-40, 85), "Humidity": (0, 100), "Pressure": (300, 1100)}   # these are the limits of the BME280 sensor


influx_client = InfluxDBClient(
    url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker\n")
        for key, (lo, hi) in LIMITS.items():
            print(f"{key} limits: min {lo}, max {hi}")
        print(f"Intervals: normal {normal_interval} ms, fast {fast_interval} ms\n")
        print(f"Interval is set at {normal_interval}.\n")
        client.subscribe(STATUS_TOPIC)
        client.subscribe(TELEMETRY_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global current_interval
    try:
        if msg.topic == STATUS_TOPIC:
            status = msg.payload.decode()
            print(f"Device {device_id} is {status}")
            if status == "online":
                current_interval = None 
            return
        
        data = json.loads(msg.payload.decode())
        point = Point("sensor").tag("device", device_id)
        for key in ("Temperature", "Humidity", "Pressure"):
            if key in data:
                point = point.field(key, float(data[key]))
        point = point.time(datetime.now(timezone.utc))
        write_api.write(bucket=INFLUX_BUCKET, record=point)

        print("\n")
        print(f"Device {device_id} - {device_location}")
        print("==================================")
        print("Saving measurements to database:")
        print(f"Temperature: {data['Temperature']} °C")
        print(f"Humidity: {data['Humidity']} %")
        print(f"Pressure: {data['Pressure']} hPa")
        print("==================================\n")
        
        anomalies = find_anomalies(data)
        for reason in find_anomalies(data):
                report_anomaly(client, reason)
        if not any("invalid" in a for a in anomalies): 
            check_thresholds(client, data)
    except Exception as e:
        print(f"Error: {e}")
    
    
def find_violations(data):
    result = []
    for key, (minimum, maximum) in LIMITS.items():
        measurement = data.get(key)
        if measurement is None:
            continue
        if measurement > maximum:
            result.append(f"{key} {measurement} above max {maximum}")
        elif measurement < minimum:
            result.append(f"{key} {measurement} below min {minimum}")
    return result


def check_thresholds(client, data):
    global current_interval
    violations = find_violations(data)
    if violations:
        desired_interval = fast_interval
    elif not violations:
        desired_interval = normal_interval

    if desired_interval != current_interval:
        cmd_payload = json.dumps({"interval_ms": desired_interval})
        client.publish(CMD_TOPIC, cmd_payload, qos=1)
        current_interval = desired_interval
        if violations:
            for i in violations:
                print(f"[WRN] Device - {device_id}: {i}.")
        print(f"[CMD] Changed interval to {current_interval}.\n")

def find_anomalies(data):
    global last_temp, same_count
    problems = []

    for key, (minimum, maximum) in RANGES.items():
        measurement = data.get(key)
        if measurement is None or math.isnan(measurement) or not (minimum <= measurement <= maximum):
            problems.append(f"{key} invalid or out of range: {measurement}")

    temperature = data.get("Temperature")
    if temperature is not None and not math.isnan(temperature) and last_temp is not None:
        if abs(temperature - last_temp) > max_jump:
            problems.append(f"Temperature jumped {temperature - last_temp:+.2f} °C.")
        same_count = same_count + 1 if temperature == last_temp else 0
        if same_count >= frozen_count:
            problems.append(f"Temperature frozen at {temperature} for {same_count} readings")
    last_temp = temperature
    return problems

def report_anomaly(client, reason):
    print(f"[ANOMALY] {device_id}: {reason}")
    client.publish(ANOMALY_TOPIC, json.dumps({"device": device_id, "reason": reason}), qos=1)
    point = Point("anomaly").tag("device", device_id).field("reason", reason)
    point = point.time(datetime.now(timezone.utc))
    write_api.write(bucket=INFLUX_BUCKET, record=point)
        
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    print("\nConnecting to MQTT broker...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
