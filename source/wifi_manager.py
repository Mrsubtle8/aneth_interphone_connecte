import network
from time import sleep
from machine import Pin
from config import WIFI_NAME, WIFI_PASSWORD

led = Pin("LED", Pin.OUT)

def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connexion Wi-Fi...")
        wlan.connect(WIFI_NAME, WIFI_PASSWORD)

    while not wlan.isconnected():
        led.toggle()
        sleep(0.3)

    led.on()
    print("Wi-Fi OK:", wlan.ifconfig())
    return wlan