# config_store.py - Configuration persistante (config.json)
#
# Tous les parametres editables via la page web sont stockes dans config.json.
# Les valeurs d'usine (defauts) viennent de config.py : au premier demarrage,
# si config.json n'existe pas encore, on utilise ces defauts.
#
# config.json n'est JAMAIS inclus dans l'OTA (manifest) : il reste local a
# l'appareil et n'est jamais ecrase par une mise a jour.

import json
import config

CONFIG_FILE = "config.json"

# Schema complet + valeurs d'usine. Toute cle ajoutee ici devient editable/
# sauvegardable. On part des constantes de config.py pour ne rien dupliquer.
DEFAULTS = {
    # Wi-Fi
    "wifi_name": config.WIFI_NAME,
    "wifi_password": config.WIFI_PASSWORD,
    # Pushover
    "pushover_user_key": config.PUSHOVER_USER_KEY,
    "pushover_api_token": config.PUSHOVER_API_TOKEN,
    "pushover_priority": config.PUSHOVER_PRIORITY,
    "pushover_retry": config.PUSHOVER_RETRY,
    "pushover_expire": config.PUSHOVER_EXPIRE,
    "pushover_sound": config.PUSHOVER_SOUND,
    "message": config.MESSAGE,
    # Acces web
    "web_password": config.WEB_PASSWORD,
    # Broches
    "detect_pin": config.DETECT_PIN,
    "relay_pin": config.RELAY_PIN,
    # Relais
    "relay_active_low": config.RELAY_ACTIVE_LOW,
    "relay_pulse_ms": config.RELAY_PULSE_MS,
    # Interphone
    "anti_double_ms": config.ANTI_DOUBLE_MS,
    # Notification : bouton "Ouvrir la porte" dans la notif Pushover
    "notify_open_url": True,
    # Base de l'URL d'ouverture. Vide -> http://<ip locale> (marche en Wi-Fi
    # local). Renseigner une URL externe pour ouvrir hors du reseau (port
    # forwarding / DDNS / VPN), ex http://moncompte.duckdns.org:8080
    "open_url_base": "",
    # OTA (mise a jour via GitHub)
    "ota_repo": "Mrsubtle8/aneth_interphone_connecte",
    "ota_branch": "main",
    "ota_path": "source/",
}


def load():
    """Renvoie la config courante : defauts + valeurs sauvegardees."""
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
        for k, v in saved.items():
            if k in cfg:  # ignore les cles inconnues
                cfg[k] = v
    except (OSError, ValueError):
        pass  # pas de config.json -> defauts
    return cfg


def save(cfg):
    """Sauvegarde uniquement les cles connues dans config.json."""
    out = {}
    for k in DEFAULTS:
        if k in cfg:
            out[k] = cfg[k]
    with open(CONFIG_FILE, "w") as f:
        json.dump(out, f)
