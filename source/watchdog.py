# watchdog.py - Filet de securite : watchdog materiel + redemarrages traces
#
# - start()       : watchdog materiel. Si la boucle principale ne le "nourrit"
#                   plus pendant ~8-16 s (blocage), la puce redemarre seule.
# - feed()        : a appeler dans la boucle et pendant les operations longues.
# - reboot(cause) : redemarrage volontaire, en notant la cause.
# - boot_reason() : cause du dernier redemarrage (lue au demarrage).
# - maintenance() : apres un Ctrl-C (Thonny), nourrit le watchdog en tache de
#                   fond pour pouvoir travailler en USB sans redemarrage.

import machine
import time
from time import ticks_ms, ticks_diff

REASON_FILE = "reboot_reason.txt"
CRASH_FILE = "crash.log"

_wdt = None
_timer = None
last_reason = "?"

_up_ms = 0
_up_last = ticks_ms()


def start(enabled=True):
    """Demarre le watchdog materiel avec le plus long delai accepte."""
    global _wdt
    if not enabled or _wdt is not None:
        return
    for t in (16000, 8300):  # RP2350 ~16 s ; RP2040 ~8 s maximum
        try:
            _wdt = machine.WDT(timeout=t)
            print("Watchdog actif (%d ms)" % t)
            return
        except Exception:  # noqa: BLE001
            pass
    print("Watchdog indisponible")


def active():
    return _wdt is not None


def feed():
    if _wdt is not None:
        _wdt.feed()


def maintenance():
    """Mode maintenance : watchdog nourri par un timer, REPL utilisable."""
    global _timer
    if _wdt is None or _timer is not None:
        return
    _timer = machine.Timer(mode=machine.Timer.PERIODIC, period=2000,
                           callback=lambda t: _wdt.feed())
    print("Mode maintenance : watchdog maintenu, REPL / Thonny disponibles.")


def uptime_s():
    """Temps depuis le demarrage (s). Appele au moins chaque minute."""
    global _up_ms, _up_last
    now = ticks_ms()
    _up_ms += ticks_diff(now, _up_last)
    _up_last = now
    return _up_ms // 1000


def reboot(reason):
    """Redemarrage volontaire : la cause est notee pour le prochain demarrage."""
    print("Redemarrage :", reason)
    try:
        with open(REASON_FILE, "w") as f:
            f.write(reason)
    except OSError:
        pass
    time.sleep(0.2)
    machine.reset()


def boot_reason():
    """Cause du dernier redemarrage (a appeler une seule fois, au demarrage)."""
    global last_reason
    reason = None
    try:
        with open(REASON_FILE) as f:
            reason = f.read().strip()
        import os
        os.remove(REASON_FILE)
    except OSError:
        pass
    if not reason:
        if machine.reset_cause() == machine.WDT_RESET:
            reason = "blocage detecte (watchdog)"
        else:
            reason = "mise sous tension"
    last_reason = reason
    return reason


def log_crash(exc):
    """Garde la trace d'une erreur imprevue dans crash.log (fichier court)."""
    import sys
    sys.print_exception(exc)
    try:
        try:
            with open(CRASH_FILE) as f:
                old = f.read()[-1500:]
        except OSError:
            old = ""
        with open(CRASH_FILE, "w") as f:
            f.write(old)
            f.write("\n--- uptime %d s ---\n" % uptime_s())
            sys.print_exception(exc, f)
    except Exception:  # noqa: BLE001
        pass
