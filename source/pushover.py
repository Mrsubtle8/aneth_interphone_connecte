import urequests
import gc
from config import (
    PUSHOVER_USER_KEY,
    PUSHOVER_API_TOKEN,
    PUSHOVER_PRIORITY,
    PUSHOVER_RETRY,
    PUSHOVER_EXPIRE,
    PUSHOVER_SOUND,
)

def urlencode(text):
    text = str(text)
    text = text.replace(" ", "%20")
    text = text.replace("'", "%27")
    text = text.replace("é", "e")
    text = text.replace("è", "e")
    text = text.replace("à", "a")
    text = text.replace("ç", "c")
    return text

def send(message):
    gc.collect()

    data = (
        "token=" + PUSHOVER_API_TOKEN +
        "&user=" + PUSHOVER_USER_KEY +
        "&title=Interphone%20Pickles" +
        "&message=" + urlencode(message) +
        "&priority=" + str(PUSHOVER_PRIORITY) +
        "&sound=" + PUSHOVER_SOUND
    )

    if PUSHOVER_PRIORITY == 2:
        data += (
            "&retry=" + str(PUSHOVER_RETRY) +
            "&expire=" + str(PUSHOVER_EXPIRE)
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