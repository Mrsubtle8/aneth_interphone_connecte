from machine import Pin
from time import sleep
import config_store

_cfg = config_store.load()
RELAY_ACTIVE_LOW = _cfg["relay_active_low"]
RELAY_PULSE_MS = _cfg["relay_pulse_ms"]

relay = Pin(_cfg["relay_pin"], Pin.OUT)

def off():
    relay.value(1 if RELAY_ACTIVE_LOW else 0)

def on():
    relay.value(0 if RELAY_ACTIVE_LOW else 1)

def pulse():
    print("Ouverture relais")
    on()
    sleep(RELAY_PULSE_MS / 1000)
    off()

off()
