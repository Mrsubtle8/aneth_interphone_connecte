# telegram.py - Acces distant via bot Telegram (ouverture de porte)
#
# Le Pico interroge Telegram en SORTANT (comme pushover.py) : rien n'est expose
# sur internet. Seuls les messages / boutons provenant du chat_id autorise sont
# honores. Le token du bot reste local (config.json).
#
# - notify(text) : envoie un message avec un bouton inline "Ouvrir la porte"
# - poll()       : recupere les updates (commande /ouvrir ou bouton) et ouvre
#                  la porte si l'expediteur est autorise. Throttle interne.

import urequests
import gc
from time import ticks_ms, ticks_diff

import config_store
import relay

API = "https://api.telegram.org/bot"

# Intervalle de polling (ms). timeout=0 cote API -> retour immediat.
POLL_INTERVAL_MS = 3000

_last_poll = 0
_offset = None  # None = pas encore initialise (on saute le backlog au 1er poll)


def _request(token, method, params):
    """Appel API Telegram. Renvoie le dict 'result' ou None en cas d'echec."""
    gc.collect()
    url = API + token + "/" + method
    if params:
        url += "?" + params
    r = None
    try:
        r = urequests.get(url)
        data = r.json()
        return data.get("result") if data.get("ok") else None
    except Exception as e:  # noqa: BLE001
        print("Telegram erreur:", e)
        return None
    finally:
        if r:
            r.close()
        gc.collect()


def _q(text):
    """Encodage minimal pour un parametre d'URL (espaces, accents, &, etc.)."""
    out = ""
    for ch in str(text):
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch in "-_.~":
            out += ch
        else:
            o = ord(ch)
            if o < 128:
                out += "%%%02X" % o
            else:
                for b in ch.encode("utf-8"):
                    out += "%%%02X" % b
    return out


# Clavier inline avec un bouton "Ouvrir la porte" (callback_data="open").
_OPEN_KEYBOARD = '{"inline_keyboard":[[{"text":"🔓 Ouvrir la porte","callback_data":"open"}]]}'


def notify(text):
    """Envoie un message Telegram avec le bouton d'ouverture."""
    cfg = config_store.load()
    if not cfg.get("telegram_enabled") or not cfg.get("telegram_bot_token") \
            or not cfg.get("telegram_chat_id"):
        return
    params = (
        "chat_id=" + str(cfg["telegram_chat_id"]) +
        "&text=" + _q(text) +
        "&reply_markup=" + _q(_OPEN_KEYBOARD)
    )
    _request(cfg["telegram_bot_token"], "sendMessage", params)


def _send_text(cfg, text):
    params = "chat_id=" + str(cfg["telegram_chat_id"]) + "&text=" + _q(text)
    _request(cfg["telegram_bot_token"], "sendMessage", params)


def _open_door(cfg, source):
    print("Telegram: ouverture porte (" + source + ")")
    relay.pulse()
    _send_text(cfg, "🔓 Porte ouverte")


def poll():
    """Recupere les updates et traite les commandes/boutons autorises.

    No-op si Telegram est desactive ou si l'intervalle n'est pas ecoule.
    """
    global _last_poll, _offset

    cfg = config_store.load()
    if not cfg.get("telegram_enabled") or not cfg.get("telegram_bot_token"):
        return

    now = ticks_ms()
    if ticks_diff(now, _last_poll) < POLL_INTERVAL_MS:
        return
    _last_poll = now

    token = cfg["telegram_bot_token"]
    allowed = str(cfg.get("telegram_chat_id", ""))

    # Mode association : pas encore de chat_id -> le bot apprend le tien au
    # premier message recu (on lit le backlog pour capter un message deja
    # envoye). Premier message gagne, puis c'est verrouille.
    if not allowed:
        if _offset is None:
            _offset = 0
        updates = _request(token, "getUpdates",
                           'offset=%d&timeout=0&allowed_updates=%s' % (_offset, _q('["message"]')))
        if not updates:
            return
        for up in updates:
            _offset = up["update_id"] + 1
            msg = up.get("message")
            if msg and msg.get("from", {}).get("id") is not None:
                chat_id = str(msg["from"]["id"])
                cfg["telegram_chat_id"] = chat_id
                config_store.save(cfg)
                _send_text(cfg, "Appareil associe a ton compte. Envoie /ouvrir pour ouvrir la porte.")
                print("Telegram: associe au chat_id", chat_id)
                return
        return

    # Au tout premier poll (chat_id deja connu) : on avance l'offset au-dela du
    # backlog pour ne pas rejouer une commande recue pendant que le Pico etait eteint.
    if _offset is None:
        updates = _request(token, "getUpdates", "offset=-1&timeout=0")
        if updates:
            _offset = updates[-1]["update_id"] + 1
        else:
            _offset = 0
        return

    params = 'offset=%d&timeout=0&allowed_updates=%s' % (
        _offset, _q('["message","callback_query"]'))
    updates = _request(token, "getUpdates", params)
    if not updates:
        return

    for up in updates:
        _offset = up["update_id"] + 1
        try:
            if "callback_query" in up:
                cb = up["callback_query"]
                from_id = str(cb.get("from", {}).get("id", ""))
                cb_id = cb.get("id", "")
                if from_id == allowed and cb.get("data") == "open":
                    _open_door(cfg, "bouton")
                    _request(token, "answerCallbackQuery",
                             "callback_query_id=" + cb_id + "&text=" + _q("Porte ouverte"))
                else:
                    _request(token, "answerCallbackQuery", "callback_query_id=" + cb_id)
            elif "message" in up:
                msg = up["message"]
                from_id = str(msg.get("from", {}).get("id", ""))
                text = msg.get("text", "")
                if from_id != allowed:
                    continue
                low = text.strip().lower()
                if low in ("/ouvrir", "/open", "/ouvrir@", "ouvrir"):
                    _open_door(cfg, "commande")
                elif low in ("/start", "/aide", "/help"):
                    _send_text(cfg, "Interphone Pickles. Envoie /ouvrir pour ouvrir la porte.")
        except Exception as e:  # noqa: BLE001
            print("Telegram traitement:", e)
        gc.collect()
