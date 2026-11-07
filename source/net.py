# net.py - Requetes HTTP(S) avec timeout, watchdog et suivi de sante
#
# Toutes les requetes sortantes (Telegram, Pushover, surveillance) passent ici :
#   - timeout sur chaque operation reseau (plus de blocage infini)
#   - watchdog nourri avant/apres
#   - succes / echec signales a health.py

import gc
from time import ticks_ms, ticks_diff
import urequests
import config_store
import watchdog
import health

TIMEOUT = 4          # s par operation reseau (connexion, envoi, lecture)
_timeout_ok = True   # False si l'urequests du firmware ne connait pas timeout


def _call(fn, url, **kw):
    global _timeout_ok
    watchdog.feed()
    gc.collect()
    try:
        if _timeout_ok:
            try:
                r = fn(url, timeout=TIMEOUT, **kw)
            except TypeError:
                _timeout_ok = False
                r = fn(url, **kw)
        else:
            r = fn(url, **kw)
    except Exception:
        health.fail()
        watchdog.feed()
        raise
    health.ok()
    watchdog.feed()
    return r


def get(url, **kw):
    return _call(urequests.get, url, **kw)


def post(url, **kw):
    return _call(urequests.post, url, **kw)


# Surveillance externe (ex : healthchecks.io) : un ping toutes les 5 min.
# Si le ping s'arrete, c'est le service externe qui te previent.
BEAT_MS = 5 * 60 * 1000
_last_beat = None


def heartbeat():
    global _last_beat
    now = ticks_ms()
    if _last_beat is not None and ticks_diff(now, _last_beat) < BEAT_MS:
        return
    _last_beat = now
    url = config_store.load().get("heartbeat_url", "")
    if not url:
        return
    try:
        r = get(url)
        r.close()
    except Exception as e:  # noqa: BLE001
        print("Surveillance:", e)
