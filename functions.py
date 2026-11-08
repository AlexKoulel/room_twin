import json
import math
from datetime import datetime, timezone
import yaml
from influxdb_client import Point



def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def load_yaml(path):
   with open(path, "r") as f:
    return yaml.load(f, Loader=yaml.SafeLoader)

def find_violations(data, limits):
    result = []
    for key, (minimum, maximum) in limits.items():
        measurement = data.get(key)
        if measurement is None:
            continue
        if measurement > maximum:
            result.append(f"{key} {measurement} above max {maximum}")
        elif measurement < minimum:
            result.append(f"{key} {measurement} below min {minimum}")
    return result

def find_range_problems(data, ranges):
    problems = []
    for key, (minimum, maximum) in ranges.items():
        measurement = data.get(key)
        if measurement is None or math.isnan(measurement) or not (minimum <= measurement <= maximum):
            problems.append(f"{key} invalid or out of range: {measurement}")
    return problems

def sensor_point(device_id, data):
    point = Point("sensor").tag("device", device_id)
    for key in ("Temperature", "Humidity", "Pressure", "TPrediction","Residual"):
        if key in data:
            point = point.field(key, float(data[key]))
    return point.time(datetime.now(timezone.utc))

def anomaly_point(device_id, reason):
    point = Point("anomaly").tag("device", device_id).field("reason", reason)
    return  point.time(datetime.now(timezone.utc))