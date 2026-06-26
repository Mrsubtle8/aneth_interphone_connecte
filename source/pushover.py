import urequests
import gc
import config_store

# Caracteres non encodes en percent-encoding (RFC 3986 unreserved).
_SAFE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~"

def quote(s):
    """Percent-encode complet (pour la valeur du parametre url)."""
    out = ""
    for ch in str(s):
        if ch in _SAFE:
            out += ch
        else:
            o = ord(ch)
            if o < 128:
                out += "%%%02X" % o
            else:
                for b in ch.encode("utf-8"):
                    out += "%%%02X" % b
    return out

def message_encode(text):
    """Encodage simple du message (espaces + accents retires)."""
    text = str(text)
    text = text.replace(" ", "%20")
    text = text.replace("'", "%27")
    text = text.replace("é", "e")
    text = text.replace("è", "e")
    text = text.replace("à", "a")
    text = text.replace("ç", "c")
    return text

def send(message=None, ip=None):
    gc.collect()
    cfg = config_store.load()

    if message is None:
        message = cfg["message"]

    priority = int(cfg["pushover_priority"])

    data = (
        "token=" + cfg["pushover_api_token"] +
        "&user=" + cfg["pushover_user_key"] +
        "&title=Interphone%20Pickles" +
        "&message=" + message_encode(message) +
        "&priority=" + str(priority) +
        "&sound=" + cfg["pushover_sound"]
    )

    if priority == 2:
        data += (
            "&retry=" + str(cfg["pushover_retry"]) +
            "&expire=" + str(cfg["pushover_expire"])
        )

    # Lien "Ouvrir la porte" dans la notification (parametres Pushover
    # url / url_title). Base = URL externe configuree, sinon l'IP locale.
    if cfg.get("notify_open_url", True):
        base = cfg.get("open_url_base", "")
        if not base and ip:
            base = "http://" + ip
        if base:
            open_url = base.rstrip("/") + "/open?password=" + cfg["web_password"]
            data += "&url=" + quote(open_url)
            data += "&url_title=" + quote("Ouvrir la porte")

    try:
        r = urequests.post(
            "https://api.pushover.net/1/messages.json",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        status = r.status_code
        r.close()
        del r
        gc.collect()
        print("Pushover:", status)
        return status == 200

    except Exception as e:
        gc.collect()
        print("Erreur Pushover:", e)
        return False
