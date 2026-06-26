# history.py - Journal local des evenements (sonneries + ouvertures)
#
# Les evenements sont enregistres sur le Pico (fichier, anneau des N derniers),
# meme sans reseau : on garde une trace de chaque sonnerie / ouverture avec
# l'heure de Paris (passage ete/hiver automatique). L'heure vient du NTP
# synchronise au demarrage (cf main.py).

import json
import time

HIST_FILE = "history.json"
HIST_MAX = 30


def _load():
    try:
        with open(HIST_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def add(kind, info=""):
    """Ajoute un evenement. kind = 'sonnerie' ou 'ouverture'."""
    evs = _load()
    evs.append({"t": time.time(), "k": kind, "i": info})
    evs = evs[-HIST_MAX:]
    try:
        with open(HIST_FILE, "w") as f:
            json.dump(evs, f)
    except OSError:
        pass


def recent(n=15):
    """Les n evenements les plus recents (plus recent en premier)."""
    evs = _load()
    evs.reverse()
    return evs[:n]


# --------------------------------------------------------------------------
# Heure de Paris (CET = UTC+1, CEST = UTC+2) avec DST automatique.
# CEST du dernier dimanche de mars 01:00 UTC au dernier dimanche d'octobre.
# --------------------------------------------------------------------------
def _last_sunday(year, month):
    # jour de semaine du 31 (mars/octobre ont 31 jours) ; 0=lundi .. 6=dimanche
    wday = time.localtime(time.mktime((year, month, 31, 12, 0, 0, 0, 0)))[6]
    return 31 - ((wday + 1) % 7)


def _paris_offset(tm):
    y, m, d, hh = tm[0], tm[1], tm[2], tm[3]
    if m < 3 or m > 10:
        return 1
    if 3 < m < 10:
        return 2
    ls = _last_sunday(y, m)
    if m == 3:
        return 2 if (d > ls or (d == ls and hh >= 1)) else 1
    return 1 if (d > ls or (d == ls and hh >= 1)) else 2


def fmt_time(epoch):
    tm = time.localtime(epoch)               # UTC
    off = _paris_offset(tm)
    tm = time.localtime(epoch + off * 3600)  # Paris
    return "%02d/%02d %02d:%02d" % (tm[2], tm[1], tm[3], tm[4])


def text(n=15):
    """Historique formate (multi-lignes) pour la page web / Telegram."""
    evs = recent(n)
    if not evs:
        return "Aucun evenement enregistre."
    lines = []
    for e in evs:
        label = "Sonnerie" if e.get("k") == "sonnerie" else "Ouverture"
        extra = " (" + e["i"] + ")" if e.get("i") else ""
        # Si l'horloge n'a pas ete synchronisee (annee < 2023), on le signale.
        when = fmt_time(e["t"]) if e["t"] > 730000000 else "??/?? --:--"
        lines.append(when + "  " + label + extra)
    return "\n".join(lines)
