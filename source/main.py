from time import sleep, ticks_ms, ticks_diff
from machine import Pin

import wifi_manager
import pushover
import relay
import interphone
import web
import telegram
import history

led = Pin("LED", Pin.OUT)

print("MAIN.PY DEMARRE")

wifi = wifi_manager.connect()
ip = wifi.ifconfig()[0]


def sync_time():
    """Synchronise l'horloge par NTP (pour horodater l'historique)."""
    try:
        import ntptime
        ntptime.settime()
        print("NTP OK")
    except Exception as e:  # noqa: BLE001
        print("NTP echec:", e)


sync_time()
_last_ntp = ticks_ms()
NTP_RESYNC_MS = 6 * 3600 * 1000  # resync toutes les 6 h

sock = web.start()

print("===================================")
print(" Interphone Pickles V2 pret")
print(" Page web : http://" + ip)
print("===================================")


def on_ring():
    """Sonnerie detectee : notifie (Pushover + Telegram) et journalise,
    meme si le reseau est absent (l'evenement est garde localement)."""
    print(">>> SONNERIE DETECTEE <<<")
    ok = False
    try:
        ok = bool(pushover.send(ip=ip))
    except Exception as e:  # noqa: BLE001
        print("Pushover:", e)
    try:
        if telegram.notify("Quelqu'un sonne a la porte"):
            ok = True
    except Exception as e:  # noqa: BLE001
        print("Telegram:", e)
    history.add("sonnerie", "notif OK" if ok else "hors reseau")


while True:
    if wifi.isconnected():
        ip = wifi.ifconfig()[0]
        # Resync NTP periodique
        if ticks_diff(ticks_ms(), _last_ntp) > NTP_RESYNC_MS:
            sync_time()
            _last_ntp = ticks_ms()
    else:
        # Reconnexion non bloquante : la detection de sonnerie continue.
        if wifi_manager.reconnect(wifi):
            ip = wifi.ifconfig()[0]
            sync_time()
            _last_ntp = ticks_ms()

    web.step(sock, ip)

    telegram.poll()

    if interphone.check():
        on_ring()

    led.value(1 if interphone.is_active() else 0)

    sleep(0.02)
