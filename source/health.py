# health.py - Surveillance de la connexion (Wi-Fi "zombie", reseau bloque)
#
# Chaque requete reseau signale ok() ou fail(). Si plus rien ne passe :
#   - apres 5 min : on relance le Wi-Fi (cas du Wi-Fi "connecte" mais muet)
#   - apres 10 min : redemarrage du Pico
# Pendant une vraie panne internet, le delai double a chaque redemarrage
# (10, 20, 40, 80 min puis 2 h max) pour ne pas redemarrer en boucle.

from time import ticks_ms, ticks_diff
import watchdog

WIFI_RESET_MS = 5 * 60 * 1000
REBOOT_MS = 10 * 60 * 1000
MAX_REBOOT_MS = 120 * 60 * 1000
COUNT_FILE = "net_reboots.txt"

_fail_since = None
_disc_since = None
_wifi_reset_done = False
_net_reboots = 0

try:
    with open(COUNT_FILE) as f:
        _net_reboots = int(f.read().strip() or "0")
except (OSError, ValueError):
    _net_reboots = 0


def _reboot_delay():
    return min(REBOOT_MS * (2 ** min(_net_reboots, 4)), MAX_REBOOT_MS)


def ok():
    """Une requete reseau a abouti."""
    global _fail_since, _wifi_reset_done, _net_reboots
    _fail_since = None
    _wifi_reset_done = False
    if _net_reboots:
        _net_reboots = 0
        try:
            import os
            os.remove(COUNT_FILE)
        except OSError:
            pass


def fail():
    """Une requete reseau a echoue."""
    global _fail_since
    if _fail_since is None:
        _fail_since = ticks_ms()


def _net_reboot(reason):
    try:
        with open(COUNT_FILE, "w") as f:
            f.write(str(_net_reboots + 1))
    except OSError:
        pass
    watchdog.reboot(reason)


def check(wlan, wifi_reset):
    """A appeler a chaque tour de la boucle principale (tres leger)."""
    global _disc_since, _wifi_reset_done, _fail_since
    now = ticks_ms()
    if not wlan.isconnected():
        # Hors ligne : les echecs de requetes sont normaux, on ne les compte
        # pas (la deconnexion a son propre minuteur ci-dessous).
        _fail_since = None
        if _disc_since is None:
            _disc_since = now
        elif ticks_diff(now, _disc_since) > _reboot_delay():
            _net_reboot("Wi-Fi perdu trop longtemps")
        return
    _disc_since = None
    if _fail_since is None:
        return
    d = ticks_diff(now, _fail_since)
    if d > _reboot_delay():
        _net_reboot("reseau bloque (plus aucune reponse)")
    elif d > WIFI_RESET_MS and not _wifi_reset_done:
        _wifi_reset_done = True
        print("Reseau muet depuis 5 min : relance du Wi-Fi")
        wifi_reset(wlan)


def status():
    if _fail_since is None:
        return "OK"
    return "echecs depuis %d min" % (ticks_diff(ticks_ms(), _fail_since) // 60000)
