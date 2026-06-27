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
import history

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
    return _request(cfg["telegram_bot_token"], "sendMessage", params) is not None


def _send_text(cfg, text):
    params = "chat_id=" + str(cfg["telegram_chat_id"]) + "&text=" + _q(text)
    _request(cfg["telegram_bot_token"], "sendMessage", params)


def _open_door(cfg, source):
    print("Telegram: ouverture porte (" + source + ")")
    relay.pulse()
    history.add("ouverture", "Telegram " + source)
    _send_text(cfg, "🔓 Porte ouverte")


def _norm(text):
    """Minuscule + retrait des accents, pour une reconnaissance tolerante."""
    t = str(text).strip().lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("â", "a"),
                 ("ç", "c"), ("î", "i"), ("ô", "o"), ("û", "u")):
        t = t.replace(a, b)
    return t


# Clavier persistant (boutons en bas du chat) : plus besoin de retenir les noms.
_MENU_KEYBOARD = ('{"keyboard":[["🔓 Ouvrir"],'
                  '["📜 Historique","📊 Etat"],'
                  '["🔔 Test","⬆️ Mise a jour","♻️ Redemarrer"]],'
                  '"resize_keyboard":true,"is_persistent":true}')

# Menu natif "/" de Telegram (autocompletion quand on tape "/").
_COMMANDS_JSON = ('{"commands":['
                  '{"command":"ouvrir","description":"Ouvrir la porte"},'
                  '{"command":"historique","description":"Dernieres sonneries / ouvertures"},'
                  '{"command":"etat","description":"Etat (version, IP, sonnerie)"},'
                  '{"command":"test","description":"Notification de test"},'
                  '{"command":"maj","description":"Mise a jour du firmware"},'
                  '{"command":"redemarrer","description":"Redemarrer le Pico"},'
                  '{"command":"aide","description":"Afficher le menu"}]}')

_cmds_registered = False


def _menu(cfg):
    """Envoie le message d'intro + le clavier de boutons."""
    global _cmds_registered
    txt = ("Interphone Pickles\n\n"
           "🔓 Ouvrir - ouvrir la porte\n"
           "📜 Historique - dernieres sonneries/ouvertures\n"
           "📊 Etat - version, IP, sonnerie\n"
           "🔔 Test - notification de test\n"
           "⬆️ Mise a jour - firmware (OTA)\n"
           "♻️ Redemarrer - redemarrer le Pico\n\n"
           "Utilise les boutons ci-dessous, ou tape la commande.")
    params = ("chat_id=" + str(cfg["telegram_chat_id"]) +
              "&text=" + _q(txt) +
              "&reply_markup=" + _q(_MENU_KEYBOARD))
    _request(cfg["telegram_bot_token"], "sendMessage", params)
    if not _cmds_registered:
        _request(cfg["telegram_bot_token"], "setMyCommands", "commands=" + _q(_COMMANDS_JSON))
        _cmds_registered = True


def _status(cfg):
    import fwversion
    ip = "?"
    mac = "?"
    etat = "?"
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        ip = wlan.ifconfig()[0] if wlan.isconnected() else "deconnecte"
        mac = ":".join("%02X" % b for b in wlan.config("mac"))
    except Exception:
        pass
    try:
        import interphone
        etat = "sonnerie active" if interphone.is_active() else "au repos"
    except Exception:
        pass
    _send_text(cfg, "Interphone Pickles\nVersion: %s\nIP: %s\nMAC: %s\nEtat: %s"
               % (fwversion.VERSION, ip, mac, etat))


def _test(cfg):
    import pushover
    pushover.send("Test notification interphone.")
    _send_text(cfg, "🔔 Notification de test envoyee")


def _update(cfg):
    import ota
    _send_text(cfg, "Recherche de mise a jour...")
    res = ota.check_and_update(cfg["ota_repo"], cfg.get("ota_branch", "main"),
                               cfg.get("ota_path", ""))
    if res["error"]:
        _send_text(cfg, "Erreur MAJ : " + res["error"])
    elif res["updated"]:
        _send_text(cfg, "Mis a jour vers %s. Redemarrage..." % res["version"])
        import machine
        machine.reset()
    else:
        _send_text(cfg, "Deja a jour (version %s)" % res["version"])


def _reboot(cfg):
    _send_text(cfg, "♻️ Redemarrage...")
    import machine
    machine.reset()


def _handle_text(cfg, text):
    """Reconnait une commande (texte libre, slash, ou bouton) et l'execute."""
    t = _norm(text)
    if "ouvr" in t or "open" in t:
        _open_door(cfg, "commande")
    elif "histor" in t:
        _send_text(cfg, "📜 Historique\n\n" + history.text(15))
    elif "etat" in t or "status" in t:
        _status(cfg)
    elif "test" in t:
        _test(cfg)
    elif "maj" in t or "update" in t or "mise a jour" in t:
        _update(cfg)
    elif "redemarr" in t or "reboot" in t:
        _reboot(cfg)
    else:
        # Tout le reste (/start, /aide, ou message inconnu) -> on affiche le menu.
        _menu(cfg)


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
                _send_text(cfg, "Appareil associe a ton compte.")
                _menu(cfg)
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
                _handle_text(cfg, text)
        except Exception as e:  # noqa: BLE001
            print("Telegram traitement:", e)
        gc.collect()
