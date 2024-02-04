#!/usr/bin/env python2
import sys
import subprocess
import time
import datetime

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

while True:
  for room in rooms_settings:
    if not rooms_settings[room]["enabled"]:
      continue
    target = rooms_settings[room][target_name]
    returned_output = subprocess.check_output(["/usr/bin/owread", "-s", "localhost:4304", rooms_settings[room]["sensor"]])
    try:
        temperature = round(float(returned_output.strip().strip("'")), 1)
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
          print(now()+" "+room+": Starting heaters.")
          sys.stdout.flush() 
          set_relay(rooms_settings[room]["relays"], "on")
      elif temperature > target + 0.5:
        if current_state == "1":
          print(now()+" "+room+": Target temperature is "+str(target))
          print(now()+" "+room+": Current temperature is "+str(temperature))
          print(now()+" "+room+": Stopping heaters.")
          sys.stdout.flush() 
          set_relay(rooms_settings[room]["relays"], "off")
  time.sleep(600)
