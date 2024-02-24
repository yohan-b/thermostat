#!/usr/bin/env python3
import sys
import subprocess
import logging
import time
import datetime
from datetime import timezone
import requests
import json
import yaml
import sqlite3
import argparse
import signal
from threading import Event
from http.server import BaseHTTPRequestHandler
import threading
import socketserver

# As of Python 3.7 there is a method datetime.fromisoformat() which is exactly the reverse for isoformat().
# So this will no longer be necessary.
from dateutil import parser
def getDateTimeFromISO8601String(s):
    d = parser.parse(s)
    return d

from threading import Lock

xprint_lock = Lock()

def xprint(*args, **kwargs):
    """Thread safe print function"""
    with xprint_lock:
        print(*args, **kwargs)
        sys.stdout.flush()

with open('./conf.yml') as conf:
    yaml_conf = yaml.load(conf)
    targets = yaml_conf.get("targets")
    modes = yaml_conf.get("modes")
    http_port = yaml_conf.get("http_port")
    shedding_order = yaml_conf.get("shedding_order")
    rooms_settings = yaml_conf.get("rooms_settings")
    default_target = yaml_conf.get("default_target")
    relays_load = yaml_conf.get("relays_load")
    awake_hour = yaml_conf.get("awake_hour")
    sleep_hour = yaml_conf.get("sleep_hour")
    forced_mode_duration = yaml_conf.get("forced_mode_duration")
    load_shedder_interval = yaml_conf.get("load_shedder_interval")
    relay_control_interval = yaml_conf.get("relay_control_interval")
    max_load = yaml_conf.get("max_load")
    load_margin = yaml_conf.get("load_margin")

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
    return "OK"
  except Exception as e:
    logging.error(e)
    logging.error("set relay "+relay+" to "+state+": Failed to command relays board.")
    sys.stdout.flush() 
    return "KO"

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

def get_forced_mode(cur):
  cur.execute("SELECT value, timestamp FROM set_mode WHERE name='mode'")
  row = cur.fetchone()
  data = dict(zip(['value', 'timestamp'], row))
  timestamp = getDateTimeFromISO8601String(data['timestamp']).replace(tzinfo=timezone.utc).timestamp()
  # We ignore old targets but never ignore absence modes
  if data['value'] in targets and time.time() - timestamp > forced_mode_duration:
    logging.debug("Ignoring old set mode.")
    return None
  else:
    return data['value']

logging.info("====== Starting ======")
stop = Event()
last_data = {}

def handler(signum, frame):
  global stop
  logging.info("Got interrupt: "+str(signum))
  stop.set()
  logging.info("Shutdown")

signal.signal(signal.SIGTERM,handler)
signal.signal(signal.SIGINT,handler)

class MyHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    global new_forced_mode
    request = self.path[1:]
    if request in targets or request in modes:
      self.send_response(200)
      new_forced_mode = request
    else:
      self.send_response(404)
  # This rewrites the BaseHTTP logging function
  def log_message(self, format, *args):
    if verbosity == 'INFO':
      xprint("%s - - [%s] %s" %
           (self.address_string(),
            self.log_date_time_string(),
            format%args))

class WebThread(threading.Thread):
    def run(self):
        httpd.serve_forever()

# if the database file does not exist it will be created automatically 
dbconn = sqlite3.connect("./thermostat.db")
cursor = dbconn.cursor()
# we will only use name="mode" for set_mode table
# only modes that are set manually will be recorded in the database
cursor.execute("CREATE TABLE IF NOT EXISTS set_mode (name TEXT PRIMARY KEY DEFAULT 'mode' NOT NULL, \
                                                     value TEXT NOT NULL, \
                                                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)")

start_time = time.time()
last_control_time = None
new_forced_mode = None
target_name = default_target
first_loop = True

# TODO: Get Linky overload warning

#cursor.execute("SELECT * FROM set_mode")
#rows = cursor.fetchall()
#for row in rows:
#    print(row)
#sys.stdout.flush() 

httpd = socketserver.TCPServer(("", http_port), MyHandler, bind_and_activate=False)
httpd.allow_reuse_address = True
httpd.server_bind()
httpd.server_activate()
webserver_thread = WebThread()
webserver_thread.start()

while True:
  if stop.is_set():
    httpd.shutdown()
    httpd.server_close()
    dbconn.close()
    break

  if new_forced_mode is not None:
    cursor.execute("INSERT OR REPLACE INTO set_mode (value) VALUES ('"+new_forced_mode+"')")
    dbconn.commit()
    logging.info("Switch to "+new_forced_mode)
    target_name = new_forced_mode
    new_forced_mode = None
    # Force immediate action:
    last_control_time = None
  current_time = time.time()
  current_date = datetime.datetime.now()
  today_awake_time = current_date.replace(hour=int(awake_hour.split(':')[0]), minute=int(awake_hour.split(':')[1]), second=0, microsecond=0)
  today_sleep_time = current_date.replace(hour=int(sleep_hour.split(':')[0]), minute=int(sleep_hour.split(':')[1]), second=0, microsecond=0)
  forced_mode = get_forced_mode(cursor)
  if forced_mode is not None and forced_mode in targets:
    if target_name != forced_mode:
      target_name = forced_mode
      logging.info("Switch to "+forced_mode)
  else:
    if forced_mode == "long_absence":
      if target_name != "target_frost_protection" or first_loop:
        target_name = "target_frost_protection"
        logging.info("Switch to "+target_name)
    elif forced_mode == "short_absence" or first_loop:
      if target_name != "target_sleep_temperature":
        target_name = "target_sleep_temperature"
        logging.info("Switch to "+target_name)
    elif current_date > today_awake_time and current_date < today_sleep_time:
      if target_name != "target_unconfirmed_awake_temperature" and target_name != "target_awake_temperature":
        target_name = "target_unconfirmed_awake_temperature"
        logging.info("Switch to unconfirmed awake mode.")
    elif current_date < today_awake_time or current_date > today_sleep_time:
      if target_name != "target_unconfirmed_sleep_temperature" and target_name != "target_sleep_temperature":
        target_name = "target_unconfirmed_sleep_temperature"
        logging.info("Switch to unconfirmed sleep mode.")

  first_loop = False

  # Load shedder
  current_load = get_metric("Modane_elec_main_power", current_time, load_shedder_interval)
  if current_load is None:
    time.sleep(load_shedder_interval)
    continue
  elif max_load - current_load < load_margin:
    logging.warning("Load too high: "+str(current_load)+"VA")
    total_shedded = 0
    for room in shedding_order:
      current_state = relay_state(rooms_settings[room]["relays"])
      if current_state != "Failed":
        logging.debug("Got relay_state: '"+current_state+"'")
        if current_state == "1":
          result = set_relay(rooms_settings[room]["relays"], "off")
          if result == "OK":
            total_shedded += relays_load[rooms_settings[room]["relays"]]
            if max_load - current_load - total_shedded < load_margin:
              logging.info("Load should be back to normal.")
              break
       
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

logging.info("====== Ended successfully ======")

