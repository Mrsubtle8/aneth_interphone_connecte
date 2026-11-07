import network
from time import sleep, ticks_ms, ticks_diff
from machine import Pin
import config_store
import watchdog

led = Pin("LED", Pin.OUT)

_last_try = 0
RETRY_MS = 5000
BOOT_TIMEOUT_S = 60


def connect():
    """Connexion au demarrage, limitee a 60 s.

    Si le Wi-Fi n'est pas la (box qui redemarre...), on continue quand meme :
    la sonnerie est detectee et la reconnexion se fait en tache de fond.
    """
    cfg = config_store.load()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connexion Wi-Fi...")
        wlan.connect(cfg["wifi_name"], cfg["wifi_password"])

    start = ticks_ms()
    while not wlan.isconnected():
        watchdog.feed()
        led.toggle()
        sleep(0.3)
        if ticks_diff(ticks_ms(), start) > BOOT_TIMEOUT_S * 1000:
            print("Wi-Fi absent au demarrage : on continue, reconnexion en tache de fond")
            return wlan

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


def reset(wlan):
    """Relance complete du Wi-Fi (cas du Wi-Fi 'connecte' mais muet)."""
    cfg = config_store.load()
    try:
        wlan.disconnect()
    except Exception:  # noqa: BLE001
        pass
    try:
        wlan.active(False)
        watchdog.feed()
        sleep(1)
        wlan.active(True)
        wlan.connect(cfg["wifi_name"], cfg["wifi_password"])
    except Exception as e:  # noqa: BLE001
        print("Relance Wi-Fi:", e)
    watchdog.feed()
