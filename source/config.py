# Valeurs d'usine (defauts) du firmware.
#
# IMPORTANT : ce fichier est public sur GitHub -> AUCUN secret ici.
# Les vraies valeurs (mot de passe Wi-Fi, cles Pushover) sont saisies via la
# page web et stockees dans config.json, qui reste LOCAL au Pico (gitignore,
# jamais inclus dans l'OTA). config.py ne sert que de valeurs par defaut au
# tout premier demarrage.

# Wi-Fi (a renseigner via la page web)
WIFI_NAME = ""
WIFI_PASSWORD = ""

# Pushover (a renseigner via la page web)
PUSHOVER_USER_KEY = ""
PUSHOVER_API_TOKEN = ""

PUSHOVER_PRIORITY = 2
PUSHOVER_RETRY = 30
PUSHOVER_EXPIRE = 60
PUSHOVER_SOUND = "cosmic"
MESSAGE = "Quelqu'un sonne a la porte."

# Mot de passe par defaut de la page web (a changer via la page)
WEB_PASSWORD = "pickles"

DETECT_PIN = 16
RELAY_PIN = 17

RELAY_ACTIVE_LOW = False
RELAY_PULSE_MS = 300
ANTI_DOUBLE_MS = 3000
