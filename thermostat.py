#!/usr/bin/env python3
import sys
import subprocess
import logging
import time
import datetime
from datetime import timezone
import requests
import json
import argparse

# As of Python 3.7 there is a method datetime.fromisoformat() which is exactly the reverse for isoformat().
# So this will no longer be necessary.
from dateutil import parser
def getDateTimeFromISO8601String(s):
    d = parser.parse(s)
    return d

p = argparse.ArgumentParser(description='Thermostat and load shedder.')
p.add_argument("-v", "--verbosity", help="Increase output verbosity",
                    type=str, choices=['DEBUG', 'INFO', 'WARNING'], default='INFO')
args = p.parse_args()

verbosity = args.verbosity
if verbosity == 'DEBUG':
    logging.basicConfig(level=logging.DEBUG)
elif verbosity == 'INFO':
    logging.basicConfig(level=logging.INFO)
elif verbosity == 'WARNING':
    logging.basicConfig(level=logging.WARNING)

# TODO: Put those in a YAML conf file
rooms_settings = {\
            "double bedroom": {\
                               "target_awake_temperature": 20,\
                               "target_sleep_temperature": 18,\
                               "target_frost_protection": 6,\
                               "metric": "Modane_temperature_double_bedroom",\
                               "relays": "1",\
                               "enabled": True
                              },\
            "single bedroom": {\
                               "target_awake_temperature": 17,\
                               "target_sleep_temperature": 16,\
                               "target_frost_protection": 6,\
                               "metric": "Modane_temperature_single_bedroom",\
                               "relays": "3",\
                               "enabled": True
                              },\
            "living room": {\
                               "target_awake_temperature": 21,\
                               "target_sleep_temperature": 18,\
                               "target_frost_protection": 6,\
                               "metric": "Modane_temperature_living_room",\
                               "relays": "4",\
                               "enabled": True
                              },\
            "bathroom": {\
                               "target_awake_temperature": 20,\
                               "target_sleep_temperature": 19,\
                               "target_frost_protection": 6,\
                               "metric": "Modane_temperature_bathroom",\
                               "relays": "",\
                               "enabled": False
                              }
           }

# Load in VA
relays_load = {\
  "1": 1500,\
  "3": 1500,\
  "4": 2000
}

# TODO: Use POST API to set those
#target_name = "target_awake_temperature"
target_name = "target_sleep_temperature"
#target_name = "target_frost_protection"

def now():
  return "["+datetime.datetime.now().strftime("%c")+"]"

def relay_state(relay):
  try:
    returned_output = subprocess.check_output(["./relay.py", relay, "status"])
    return returned_output.strip().decode("utf-8")
  except Exception as e:
    logging.error(e)
    logging.error("relay "+relay+" status: Failed to command relays board.")
    sys.stdout.flush() 
    return "Failed"

def set_relay(relay, state):
  try:
    returned_output = subprocess.check_output(["./relay.py", relay, state])
    logging.info("set relay "+relay+" to "+state+", new global status: "+returned_output.decode("utf-8").split('\n')[1])
    sys.stdout.flush() 
  except Exception as e:
    logging.error(e)
    logging.error("set relay "+relay+" to "+state+": Failed to command relays board.")
    sys.stdout.flush() 

def get_metric(metric, current_time, interval):
  url = "http://localhost:3000/"+metric
  try:
    r = requests.get(url)
    data = json.loads(r.text)
    timestamp = getDateTimeFromISO8601String(data['timestamp']).replace(tzinfo=timezone.utc).timestamp()
    if current_time - timestamp < interval * 2:
      return data['value']
    else:
      logging.warning("WARNING: No recent load data available.")
  except Exception as e:
    logging.error(e)
  sys.stdout.flush() 
  return None

start_time = time.time()
last_control_time = None
load_shedder_interval = 10.0
relay_control_interval = 600.0

# Puissance souscrite : 6kVA
# Puissance max avant coupure (marge 30%) : 7,8kVA
# TODO: Get Linky overload warning
max_load = 7800
load_margin = 100

logging.info("====== Starting ======")

while True:
  current_time = time.time()
  # Load shedder
  current_load = get_metric("Modane_elec_main_power", current_time, load_shedder_interval)
  if current_load is None:
    time.sleep(load_shedder_interval)
    continue
  elif max_load - current_load < load_margin:
     logging.warning("Load too high.")
     # TODO: disable a chosen relay to lower load

  # Thermostat
  if last_control_time is None or current_time - last_control_time > relay_control_interval:
    last_control_time = current_time
    for room in rooms_settings:
      if not rooms_settings[room]["enabled"]:
        continue
      target = rooms_settings[room][target_name]
      logging.debug("Target: "+str(target))
      temperature = get_metric(rooms_settings[room]["metric"], current_time, relay_control_interval)
      if temperature is None:
        continue
      logging.debug(room+": "+str(temperature))
      current_state = relay_state(rooms_settings[room]["relays"])
      if current_state != "Failed":
        logging.debug("Got relay_state: '"+current_state+"'")
        if temperature < target - 0.5:
          if current_state == "0":
            logging.info(room+": Target temperature is "+str(target))
            logging.info(room+": Current temperature is "+str(temperature))
            if current_load + relays_load[rooms_settings[room]["relays"]] + load_margin > max_load:
              logging.warning(room+": Load too high cannot start heaters.")
            else:
              logging.info(room+": Starting heaters.")
              set_relay(rooms_settings[room]["relays"], "on")
            sys.stdout.flush() 
          else:
            logging.debug("Relay already on.")

        elif temperature > target + 0.5:
          if current_state == "1":
            logging.info(room+": Target temperature is "+str(target))
            logging.info(room+": Current temperature is "+str(temperature))
            logging.info(room+": Stopping heaters.")
            sys.stdout.flush() 
            set_relay(rooms_settings[room]["relays"], "off")
          else:
            logging.debug("Relay already off.")
  time.sleep(load_shedder_interval)
