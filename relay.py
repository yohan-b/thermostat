#!/usr/bin/env python2
# Pilotage GCE USB 8 Relay Board
import time
import serial
import argparse
import sys
import subprocess

parser = argparse.ArgumentParser(description='Control relays.')
parser.add_argument('relay_list', type=str,
                    help='list of relays in ["1", ..., "8"] separated by comma, no spaces. "all" means all relays.')
parser.add_argument('action', type=str, choices=['on', 'off', 'status'],
                    help='Action on the list of relays.')

args = parser.parse_args()

if args.relay_list == 'all':
  relays = [ 'RLY'+str(i) for i in range(1,9)]
else:
  relays = []
  for relay in args.relay_list.split(','):
    if relay in [ str(i) for i in range(1,9)]:
      relays.append('RLY'+relay)
    else:
      print("ERROR: Relay '"+relay+"' does not exist.")
      sys.exit(1)

if args.action == 'on':
  action = '1'
elif args.action == 'off':
  action = '0'
else:
  action = 'status'

#print(relays)

find_ttyUSB_output = subprocess.check_output(["./find_ttyUSB.sh"])
device = None
for line in find_ttyUSB_output.split("\n"):
  if "FTDI_FT232R_USB_UART_A50285BI" in line:
    device = line.split(" ")[0]
    break

if device is None:
  print ("Relay board not found.")
  sys.exit(1)


def init_serial(pPort):         
  global ser          
  ser = serial.Serial()
  ser.baudrate = 9600 
  ser.port = pPort
  ser.bytesize = 8
  ser.parity = 'N'
  ser.timeout = None
  ser.xonxoff = False
  ser.rtscts=False
  ser.dsrdtr=False
  ser.timeout = 1
  ser.open()          

  if ser.isOpen():
    pass
    #print('Connected to ' + ser.portstr) 
  else:
    print('Could not connect to ' + ser.portstr) 
    sys.exit(1)

init_serial(device)
if action != 'status':
  for relay in relays:
    ser.write(relay.encode('ascii')+action+'\r\n')
    bytes = ser.readline() 
    #print ('Renvoie :\r\n' + bytes) 

ser.write('?RLY\r\n')
answer = ser.readline()
status = ''
for char in answer:
  if char in ['0', '1']:
    status+= char
if len(status) != 8:
  print(len(status))
  print("ERROR: status cannot be parsed.")
  print('status:\r\n' + status) 
  sys.exit(1)
elif action != 'status':
  print ('status:\r\n' + status) 

if action != 'status':
  for i in range(1,9):
    relay = status[i-1]
    if relay not in ['0', '1']:
      print("ERROR: unrecognized value '"+relay+"' for relay "+str(i))
    elif relay in relays and relay != action:
      print("ERROR: wrong status '"+relay+"' for relay "+str(i))
else:
  for i in [int(relay[3]) for relay in relays]:
    relay = status[i-1]
    if relay not in ['0', '1']:
      print("ERROR: unrecognized value '"+relay+"' for relay "+str(i))
    else:
      print relay,


ser.close()
