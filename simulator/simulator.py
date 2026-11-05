import paho.mqtt.client as mqtt
import random
import json
import time
import argparse
import os
import yaml

parser = argparse.ArgumentParser()
parser.add_argument("--config",default="config.yaml")
parser.add_argument("-t",nargs=3,type=float,default=[20,25,0.1],metavar=("min","max","step"),help="Temperature maximum/minimum and step")
parser.add_argument("-hu",nargs=3,type=float,default=[50,55,0.1],metavar=("min","max","step"),help="Humidity maximum/minimum and step")
parser.add_argument("-p",nargs=3,type=float,default=[1000,1005,0.01],metavar=("min","max","step"),help="Pressure maximum/minimum and step")
args = parser.parse_args()

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(PROJECT_DIR, "connections.json")) as f:
    connections = json.load(f)
    
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), args.config)) as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)


device_id = str(config["device"]["id"])
default_interval = 5000
min_interval = 1000
max_interval = 8000

BROKER = connections["RT_MQTT_BROKER"]
PORT = connections["RT_MQTT_PORT"]
TOPIC_DATA   = connections["RT_TELEMETRY_TOPIC"].format(device_id)
TOPIC_STATUS = connections["RT_STATUS_TOPIC"].format(device_id)
TOPIC_CMD    = connections["RT_CMD_TOPIC"].format(device_id)

interval_ms = default_interval


def on_connect(client, userdata, flags, rc, properties):
    if rc.is_failure:
        print(f"Failed to connect: {rc}")
        return
    print("Connected to MQTT broker\n")
    client.publish(TOPIC_STATUS, "online", qos=1, retain=True)
    client.subscribe(TOPIC_CMD, qos=1)

def on_message(client, userdata, msg):
    global interval_ms
    try:
        cmd = json.loads(msg.payload.decode())
        if "interval_ms" in cmd:
            interval_ms = int(cmd["interval_ms"])
            if interval_ms < min_interval:
                interval_ms = min_interval
            elif interval_ms > max_interval:
                interval_ms = max_interval
        print(f"Interval is now {interval_ms} ms")
    except Exception as e:
        print(f"Exception: {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.will_set(TOPIC_STATUS, "offline",qos=1,retain=True)
client.on_connect = on_connect
client.on_message = on_message



def main():
    client.connect(BROKER,PORT, 60)
    client.loop_start()
    try:
        print("Temperature:", args.t)
        print("Humidity:", args.hu)
        print("Pressure:", args.p)
        
        temp = (args.t[0] + args.t[1]) / 2
        humi = (args.hu[0] + args.hu[1]) / 2
        pres = (args.p[0] + args.p[1]) / 2
        last = time.time()
        while True:
            temp += random.uniform(-args.t[2], args.t[2])
            humi += random.uniform(-args.hu[2], args.hu[2])
            pres += random.uniform(-args.p[2], args.p[2])
            
            values = {
                "Temperature": round(temp,2),
                "Humidity": round(humi,2),
                "Pressure": round(pres,2)
            }
            payload = json.dumps(values)
            client.publish(TOPIC_DATA,payload)
            print("Published:", payload)
            time.sleep(interval_ms / 1000)
    except KeyboardInterrupt:
        print("Stopping...");
    finally:
        client.publish(TOPIC_STATUS, "offline", qos=1, retain=True)
        time.sleep(1)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
