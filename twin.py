import math

from functions import find_violations, find_range_problems
from models.thermal import predict_temperature

RANGES = {"Temperature": (-40, 85), "Humidity": (0, 100), "Pressure": (300, 1100)} 

class Twin:
    def __init__(self, config):
        self.device_id = str(config["device"]["id"])
        self.device_location = config["device"]["location"]
        self.normal_interval = config["intervals"]["normal_ms"]
        self.fast_interval = config["intervals"]["fast_ms"]

        self.limits = {
            "Temperature": (config["thresholds"]["temperature"]["min"], config["thresholds"]["temperature"]["max"]),
            "Humidity":    (config["thresholds"]["humidity"]["min"],    config["thresholds"]["humidity"]["max"]),
            "Pressure":    (config["thresholds"]["pressure"]["min"],    config["thresholds"]["pressure"]["max"]),
        }

        self.max_jump = config["anomaly"]["max_jump"]
        self.frozen_count = config["anomaly"]["frozen_count"]
        self.max_residual = config["anomaly"]["max_residual"]

        self.t_eq = config["model"]["t_eq"]
        self.t = config["model"]["t"]

        self.current_interval = {}
        self.last_time = None
        self.last_temp = None
        self.same_count = 0

    def device_online(self):
        self.current_interval = None

    def find_anomalies(self, data):
        problems = find_range_problems(data,RANGES)

        temperature = data.get("Temperature")
        if temperature is not None and not math.isnan(temperature) and self.last_temp is not None:
            if abs(temperature - self.last_temp) > self.max_jump:
                problems.append(f"Temperature jumped {temperature - self.last_temp:+.2f} °C.")
            self.same_count = self.same_count + 1 if temperature == self.last_temp else 0
            if self.same_count >= self.frozen_count:
                problems.append(f"Temperature frozen at {temperature} for {self.same_count} readings")
        if temperature is not None and not math.isnan(temperature):
            self.last_temp = temperature
        return problems
    
    def check_thresholds(self, data):
        violations = find_violations(data,self.limits)
        if violations:
            desired_interval = self.fast_interval
        elif not violations:
            desired_interval = self.normal_interval

        new_interval = None
        if desired_interval != self.current_interval:
            self.current_interval = desired_interval
            new_interval = desired_interval 
        return violations, new_interval

    def check_residual(self, residual):
        if abs(residual) > self.max_residual:
            return f"[RESIDUAL] Residual is {residual:+.2f} which is higher than the maximum allowed of {self.max_residual}"
        return None

    def predict(self, dt):
        if self.last_temp is not None:
            return predict_temperature(self.last_temp,self.t_eq,self.t,dt)
        else: 
            print("Could not find last temperature")
            return None
