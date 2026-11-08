# Room Twin

A small digital twin of a room tested and made for the [DTaaS platform by INTO-CPS](https://github.com/INTO-CPS-Association/DTaaS). It receives temperature, humidity and pressure over MQTT either using a ESP32 with a BME280 sensor, or through the included simulator.
It compares the temperature with the prediction of a simple model and it changes the sampling interval when it detects anomalies.The twin saves all measurements and other events to InfluxDB.

## Requirements:
 - MQTT broker
 - InfluxDb 2.x
 - If you are using a real device, an Arduino IDE with PubSubClient and Adafruit BME280 libraries to install the firmware

## Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Fill in `connections.json` with your mqtt broker adress/port and the InfluxDb url/toke/org/bucket.

3. Change the config file accordingly 
| Section | Meaning |
   |---|---|
   | `device.id`, `device.location` | Id of the device must match the actual id of the device(`DEVICE_ID` in `config.h` for the ESP#2 and `id` variable for the simulator). Location is only for the console messages |
   | `intervals.normal_ms`, `intervals.fast_ms` | Sampling interval when values are normal, and when a value is outside its thresholds. |
   | `thresholds` | Allowed minimum and maximum for all the measurements |
   | `anomaly.max_jump` | Largest allowed change of temperature between two samples (°C). |
   | `anomaly.frozen_count` | How many identical temperature readings in a row count as a frozen sensor. |
   | `anomaly.max_residual` | Largest allowed difference between the measured and the predicted temperature. |
   | `model.t_eq`, `model.t` | Ambient temperature of the room and its time constant (in seconds). |

## Run with the ESP32

1. Fill `DEVICE_ID`, `WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST` in `config.h`.
2. Open `room_twin_sketch.ino` in the Arduino IDE, install the libraries listed above, and upload it.
3. Start the twin with a config whose `device.id` equals `DEVICE_ID`:

   ```
   python main.py --config config.yaml
   ```

## Run with the simulator
Start the twin in one terminal:

```
python main.py --config config_sim.yaml
```

Start the simulator in another terminal, from the folder where `simulator.py` is (it reads `connections.json` from the parent folder):

```
python simulator.py --config sim-1.yaml -t 14 16 0.0 -hu 34 36 0.1 -p 940 960 0.01 --scenario step --target 15 --noise 0.05
```
## Run in DTaaS

The `lifecycle` folder contains the scripts for the DTaaS lifecycle. Run them from the JupyterLab terminal of the workspace:

| Script | What it does |
|---|---|
| `lifecycle/create` | Installs the dependencies. |
| `lifecycle/execute [config]` | Starts the twin with the desired config (default config: `config.yaml`). Output goes to `twin.log`. |
| `lifecycle/terminate` | Stops the twin. |
| `lifecycle/clean` | Stops the twin and removes `twin.log` and `twin.pid`. |