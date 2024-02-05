#!/usr/bin/env python3
import sys
import subprocess
import time
import datetime
from datetime import timezone
import requests
import json

# As of Python 3.7 there is a method datetime.fromisoformat() which is exactly the reverse for isoformat().
# So this will no longer be necessary.
from dateutil import parser
def getDateTimeFromISO8601String(s):
    d = parser.parse(s)
    return d

# TODO: Put those in a YAML conf file
rooms_settings = {\
            "double bedroom": {\
                               "target_awake_temperature": 19,\
                               "target_sleep_temperature": 18,\
                               "target_frost_protection": 6,\
                               "sensor": "/26.A6E96B020000/temperature",\
                               "relays": "1",\
                               "enabled": True
                              },\
            "single bedroom": {\
                               "target_awake_temperature": 17,\
                               "target_sleep_temperature": 16,\
                               "target_frost_protection": 6,\
                               "sensor": "/26.3FA954020000/temperature",\
                               "relays": "3",\
                               "enabled": True
                              },\
            "living room": {\
                               "target_awake_temperature": 20,\
                               "target_sleep_temperature": 18,\
                               "target_frost_protection": 6,\
                               "sensor": "/26.23D26B020000/temperature",\
                               "relays": "4",\
                               "enabled": True
                              },\
            "bathroom": {\
                               "target_awake_temperature": 20,\
                               "target_sleep_temperature": 19,\
                               "target_frost_protection": 6,\
                               "sensor": "/26.A4C354020000/temperature",\
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
#target_name = "target_sleep_temperature"
target_name = "target_frost_protection"

def now():
  return "["+datetime.datetime.now().strftime("%c")+"]"

def relay_state(relay):
  try:
    returned_output = subprocess.check_output(["./relay.py", relay, "status"])
    return returned_output
  except:
    print(now()+" relay "+relay+" status: Failed to command relays board.")
    sys.stdout.flush() 
    return "Failed"

def set_relay(relay, state):
  try:
    returned_output = subprocess.check_output(["./relay.py", relay, state])
    print(now()+" set relay "+relay+" to "+state+", new global status: "+returned_output.split('\n')[1])
    sys.stdout.flush() 
  except:
    print(now()+" set relay "+relay+" to "+state+": Failed to command relays board.")
    sys.stdout.flush() 

print(now()+" Starting thermostat.")
sys.stdout.flush() 

start_time = time.time()
last_control_time = None
load_shedder_interval = 10.0
relay_control_interval = 600.0

# Puissance souscrite : 6kVA
# Puissance max avant coupure (marge 30%) : 7,8kVA
# TODO: Get Linky overload warning
max_load = 7800
load_margin = 100

while True:
  current_time = time.time()
  # Load shedder
  url = "http://localhost:3000/Modane_elec_main_power"
  try:
    r = requests.get(url)
    data = json.loads(r.text)
    current_load = data['value']
    if current_time - getDateTimeFromISO8601String(data['timestamp']).replace(tzinfo=timezone.utc).timestamp() < load_shedder_interval * 2:
      if max_load - current_load < load_margin:
         print("Load too high.")
         sys.stdout.flush() 
         # TODO: disable a chosen relay to lower load
    else:
      print("WARNING: No recent load data available.")
      sys.stdout.flush() 
  except Exception as e:
    print(e)
    sys.stdout.flush() 
    time.sleep(load_shedder_interval)
    continue

  # Thermostat
  if last_control_time is None or current_time - last_control_time > relay_control_interval:
    last_control_time = current_time
    for room in rooms_settings:
      if not rooms_settings[room]["enabled"]:
        continue
      target = rooms_settings[room][target_name]
      # TODO: Use sensors-polling service API instead
      returned_output = subprocess.check_output(["/usr/bin/owread", "-s", "localhost:4304", rooms_settings[room]["sensor"]])
      try:
          temperature = round(float(returned_output.decode("utf-8").strip().strip("'")), 1)
      except ValueError:
          print (now()+" "+room+": Expected temperature, got garbage: "+returned_output)
          sys.exit(1)
      #print(now()+" "+room+": "+str(temperature))
      current_state = relay_state(rooms_settings[room]["relays"])
      if current_state != "Failed":
        if temperature < target - 0.5:
          if current_state == "0":
            print(now()+" "+room+": Target temperature is "+str(target))
            print(now()+" "+room+": Current temperature is "+str(temperature))
            if current_load + relays_load[rooms_settings[room]["relays"]] + load_margin > max_load:
              print(now()+" "+room+": Load too high cannot start heaters.")
            else:
              print(now()+" "+room+": Starting heaters.")
              set_relay(rooms_settings[room]["relays"], "on")
            sys.stdout.flush() 
        elif temperature > target + 0.5:
          if current_state == "1":
            print(now()+" "+room+": Target temperature is "+str(target))
            print(now()+" "+room+": Current temperature is "+str(temperature))
            print(now()+" "+room+": Stopping heaters.")
            sys.stdout.flush() 
            set_relay(rooms_settings[room]["relays"], "off")
  time.sleep(load_shedder_interval)
