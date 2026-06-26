from machine import Pin
from time import sleep
from config import RELAY_PIN, RELAY_ACTIVE_LOW, RELAY_PULSE_MS

relay = Pin(RELAY_PIN, Pin.OUT)

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