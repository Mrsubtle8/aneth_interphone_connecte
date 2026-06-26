import network
from time import sleep
from machine import Pin
import config_store

led = Pin("LED", Pin.OUT)

def connect():
    cfg = config_store.load()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connexion Wi-Fi...")
        wlan.connect(cfg["wifi_name"], cfg["wifi_password"])

    while not wlan.isconnected():
        led.toggle()
        sleep(0.3)

    led.on()
    print("Wi-Fi OK:", wlan.ifconfig())
    return wlan
