# main.py - Interphone Pickles
#
# Fiabilite (phase 1) :
#   - watchdog materiel : si la boucle se fige, le Pico redemarre seul
#   - toute erreur imprevue est journalisee (crash.log) ; si elles se repetent,
#     redemarrage propre
#   - surveillance du reseau (health.py) : Wi-Fi relance, puis redemarrage
#   - redemarrage preventif chaque nuit (reboot_hour, heure de Paris)
#   - message Telegram "en ligne" au demarrage, avec la cause du redemarrage
#   - Ctrl-C depuis Thonny = mode maintenance (pas de redemarrage intempestif)

import watchdog          # en premier : le filet de securite avant tout le reste
import config_store

watchdog.start(config_store.load().get("watchdog_enabled", True))

import gc
from time import sleep, ticks_ms, ticks_diff
from machine import Pin

import wifi_manager
import pushover
import interphone
import web
import telegram
import history
import health
import net

led = Pin("LED", Pin.OUT)

MEM_MIN = 20000                    # RAM libre minimale (octets) avant redemarrage
CHECK_MS = 60 * 1000               # verifications de maintenance chaque minute
NTP_RESYNC_MS = 6 * 3600 * 1000    # resynchro de l'heure toutes les 6 h
ERR_MAX = 5                        # erreurs imprevues tolerees par minute


def sync_time():
    """Synchronise l'horloge par NTP (horodatage + maintenance nocturne)."""
    watchdog.feed()
    try:
        import ntptime
        ntptime.settime()
        print("NTP OK")
    except Exception as e:  # noqa: BLE001
        print("NTP echec:", e)
    watchdog.feed()


def on_ring(ip):
    """Sonnerie : notifie (Pushover + Telegram) et journalise, meme hors reseau."""
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


def maintenance_check():
    """Chaque minute : memoire, et redemarrage preventif de la nuit."""
    gc.collect()
    free = gc.mem_free()
    if free < MEM_MIN:
        watchdog.reboot("memoire faible (%d octets libres)" % free)
    up = watchdog.uptime_s()
    if interphone.is_active():
        return  # jamais pendant une sonnerie
    try:
        hour = int(config_store.load().get("reboot_hour", 4))
    except (TypeError, ValueError):
        hour = 4
    if hour < 0:
        return  # redemarrage preventif desactive
    now = history.paris_now()
    if now is not None:
        if now[3] == hour and up > 3600:
            watchdog.reboot("maintenance quotidienne")
    elif up > 24 * 3600:
        # Horloge jamais reglee (pas de NTP) : on redemarre au bout de 24 h.
        watchdog.reboot("maintenance quotidienne")


def run():
    boot_reason = watchdog.boot_reason()
    print("MAIN.PY DEMARRE - cause :", boot_reason)

    wifi = wifi_manager.connect()
    ip = wifi.ifconfig()[0]
    if wifi.isconnected():
        sync_time()
    last_ntp = ticks_ms()

    sock = web.start()

    print("===================================")
    print(" Interphone Pickles pret")
    print(" Page web : http://" + ip)
    print("===================================")

    boot_msg_pending = True
    last_check = ticks_ms()
    err_count = 0

    while True:
        watchdog.feed()
        try:
            if wifi.isconnected():
                ip = wifi.ifconfig()[0]
                if ticks_diff(ticks_ms(), last_ntp) > NTP_RESYNC_MS:
                    sync_time()
                    last_ntp = ticks_ms()
                if boot_msg_pending:
                    # Premiere connexion : on trace le redemarrage et on previent
                    # (message silencieux). La maintenance de la nuit est prevue :
                    # ni message ni entree d'historique.
                    boot_msg_pending = False
                    if boot_reason != "maintenance quotidienne":
                        import fwversion
                        history.add("demarrage", boot_reason)
                        telegram.send("✅ Interphone en ligne (v%s)\nCause : %s"
                                      % (fwversion.VERSION, boot_reason))
            else:
                # Reconnexion non bloquante : la detection de sonnerie continue.
                if wifi_manager.reconnect(wifi):
                    ip = wifi.ifconfig()[0]
                    sync_time()
                    last_ntp = ticks_ms()

            web.step(sock, ip)

            telegram.poll()

            if interphone.check():
                on_ring(ip)

            led.value(1 if interphone.is_active() else 0)

            health.check(wifi, wifi_manager.reset)
            net.heartbeat()

            if ticks_diff(ticks_ms(), last_check) > CHECK_MS:
                last_check = ticks_ms()
                err_count = 0  # fenetre d'une minute
                maintenance_check()

        except MemoryError as e:
            watchdog.log_crash(e)
            watchdog.reboot("memoire saturee")
        except Exception as e:  # noqa: BLE001
            watchdog.log_crash(e)
            err_count += 1
            if err_count >= ERR_MAX:
                watchdog.reboot("erreurs repetees")

        sleep(0.02)


try:
    run()
except KeyboardInterrupt:
    # Ctrl-C (Thonny) : le watchdog reste nourri, on peut travailler en USB.
    watchdog.maintenance()
except Exception as e:  # noqa: BLE001
    watchdog.log_crash(e)
    print("Erreur au demarrage : nouvel essai dans 30 s (Ctrl-C pour annuler)")
    try:
        for _ in range(30):
            watchdog.feed()
            sleep(1)
        watchdog.reboot("erreur au demarrage")
    except KeyboardInterrupt:
        watchdog.maintenance()
