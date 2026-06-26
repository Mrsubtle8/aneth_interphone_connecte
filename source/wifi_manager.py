import network
from time import sleep, ticks_ms, ticks_diff
from machine import Pin
import config_store

led = Pin("LED", Pin.OUT)

_last_try = 0
RETRY_MS = 5000

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

def reconnect(wlan):
    """Tentative de reconnexion NON bloquante (throttle).

    Renvoie True si connecte. Permet a la boucle principale de continuer a
    detecter la sonnerie meme si le Wi-Fi est tombe.
    """
    global _last_try
    if wlan.isconnected():
        led.on()
        return True
    led.toggle()
    now = ticks_ms()
    if ticks_diff(now, _last_try) > RETRY_MS:
        _last_try = now
        cfg = config_store.load()
        try:
            wlan.active(True)
            wlan.connect(cfg["wifi_name"], cfg["wifi_password"])
        except Exception as e:  # noqa: BLE001
            print("Reconnexion Wi-Fi:", e)
    return wlan.isconnected()
