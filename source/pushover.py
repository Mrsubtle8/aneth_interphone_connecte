import urequests
import gc
import config_store

def urlencode(text):
    text = str(text)
    text = text.replace(" ", "%20")
    text = text.replace("'", "%27")
    text = text.replace("é", "e")
    text = text.replace("è", "e")
    text = text.replace("à", "a")
    text = text.replace("ç", "c")
    return text

def send(message=None):
    gc.collect()
    cfg = config_store.load()

    if message is None:
        message = cfg["message"]

    priority = int(cfg["pushover_priority"])

    data = (
        "token=" + cfg["pushover_api_token"] +
        "&user=" + cfg["pushover_user_key"] +
        "&title=Interphone%20Pickles" +
        "&message=" + urlencode(message) +
        "&priority=" + str(priority) +
        "&sound=" + cfg["pushover_sound"]
    )

    if priority == 2:
        data += (
            "&retry=" + str(cfg["pushover_retry"]) +
            "&expire=" + str(cfg["pushover_expire"])
        )

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

    except Exception as e:
        gc.collect()
        print("Erreur Pushover:", e)
