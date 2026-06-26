# ota.py - Mise a jour OTA depuis GitHub (raw files + manifest.json)
#
# Concu pour Pico 2 W (faible RAM) :
#   - telechargement en streaming par petits blocs (jamais le fichier entier en RAM)
#   - SHA-256 calcule a la volee pendant le telechargement
#   - on ne telecharge QUE les fichiers dont le hash differe du local
#   - telechargement etage (.new) puis swap atomique -> jamais de Pico a moitie a jour
#   - gc.collect() entre chaque fichier pour limiter la fragmentation memoire
#
# Integration (ex. dans main.py) :
#   import ota, config_store
#   cfg = config_store.load()
#   res = ota.check_and_update(cfg["ota_repo"], cfg.get("ota_branch", "main"))
#   if res["updated"]:
#       import machine; machine.reset()
#
# Le manifest distant (manifest.json) liste les fichiers + leur sha256 + une version.
# Les secrets (Wi-Fi, Pushover) restent dans config.json local et ne sont JAMAIS
# touches par l'OTA (config.json n'est pas dans le manifest).

import gc
import json
import socket

try:
    import ssl  # MicroPython
except ImportError:
    import ussl as ssl

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

# Fichier local qui memorise la version installee + le hash de chaque fichier.
LOCAL_STATE = "version.json"
# Taille des blocs de lecture reseau -> flash. Petit = peu de RAM.
CHUNK = 512
# Suffixe des fichiers telecharges avant le swap final.
TMP_SUFFIX = ".new"


# --------------------------------------------------------------------------
# Etat local
# --------------------------------------------------------------------------
def _load_state():
    try:
        with open(LOCAL_STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"version": "0.0.0", "files": {}}


def _save_state(state):
    with open(LOCAL_STATE, "w") as f:
        json.dump(state, f)


def installed_version():
    """Version du firmware reellement en cours (gravee dans fwversion.py)."""
    try:
        import fwversion
        return fwversion.VERSION
    except Exception:
        return _load_state().get("version", "0.0.0")


# --------------------------------------------------------------------------
# HTTP(S) GET en streaming (sans urequests, pour controler la RAM)
# --------------------------------------------------------------------------
def _open_url(url):
    """Ouvre une connexion et renvoie (socket, content_length, chunked).

    Le corps n'est PAS lu ici : l'appelant lit le socket par blocs.
    """
    proto, _, host_path = url.partition("://")
    host, _, path = host_path.partition("/")
    path = "/" + path
    port = 443 if proto == "https" else 80

    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    s.connect(addr)
    if proto == "https":
        s = ssl.wrap_socket(s, server_hostname=host)

    req = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "User-Agent: pico-ota\r\n"
        "Accept-Encoding: identity\r\n"
        "Connection: close\r\n\r\n" % (path, host)
    )
    s.write(req.encode())

    # Lecture des en-tetes ligne par ligne (petit buffer).
    line = s.readline()
    status = int(line.split(b" ")[1])
    content_length = None
    chunked = False
    while True:
        line = s.readline()
        if line == b"\r\n" or line == b"":
            break
        low = line.lower()
        if low.startswith(b"content-length:"):
            content_length = int(line.split(b":")[1])
        elif low.startswith(b"transfer-encoding:") and b"chunked" in low:
            chunked = True

    return s, status, content_length, chunked


def _stream_to_file(url, path):
    """Telecharge url -> fichier path en streaming, renvoie le sha256 hex.

    Gere les redirections (301/302/307) renvoyees par le CDN GitHub.
    """
    redirects = 0
    while True:
        s, status, length, chunked = _open_url(url)
        if status in (301, 302, 303, 307, 308):
            # Relire les en-tetes pour Location (deja consommes) -> on rouvre.
            # Simplifie : _open_url a deja avale les en-tetes, donc on relit
            # via une 2e passe legere ci-dessous.
            s.close()
            url = _follow_location(url)
            redirects += 1
            if redirects > 5:
                raise OSError("Trop de redirections OTA")
            continue
        if status != 200:
            s.close()
            raise OSError("HTTP %d sur %s" % (status, url))
        break

    h = hashlib.sha256()
    try:
        with open(path, "wb") as f:
            if chunked:
                _read_chunked(s, f, h)
            else:
                _read_length(s, f, h, length)
    finally:
        s.close()
    gc.collect()
    return _hexlify(h.digest())


def _read_length(s, f, h, length):
    remaining = length if length is not None else -1
    while remaining != 0:
        want = CHUNK if remaining < 0 else min(CHUNK, remaining)
        block = s.read(want)
        if not block:
            break
        f.write(block)
        h.update(block)
        if remaining > 0:
            remaining -= len(block)


def _read_chunked(s, f, h):
    while True:
        size_line = s.readline().strip()
        if not size_line:
            break
        size = int(size_line.split(b";")[0], 16)
        if size == 0:
            break
        got = 0
        while got < size:
            block = s.read(min(CHUNK, size - got))
            if not block:
                break
            f.write(block)
            h.update(block)
            got += len(block)
        s.readline()  # CRLF de fin de chunk


def _follow_location(url):
    """Refait une requete pour recuperer l'en-tete Location d'une redirection."""
    proto, _, host_path = url.partition("://")
    host, _, path = host_path.partition("/")
    path = "/" + path
    port = 443 if proto == "https" else 80
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    s.connect(addr)
    if proto == "https":
        s = ssl.wrap_socket(s, server_hostname=host)
    s.write(
        ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: pico-ota\r\n"
         "Connection: close\r\n\r\n" % (path, host)).encode()
    )
    s.readline()  # status
    loc = None
    while True:
        line = s.readline()
        if line == b"\r\n" or line == b"":
            break
        if line.lower().startswith(b"location:"):
            loc = line.split(b":", 1)[1].strip().decode()
    s.close()
    if not loc:
        raise OSError("Redirection sans Location")
    return loc


def _hexlify(b):
    return "".join("%02x" % x for x in b)


# --------------------------------------------------------------------------
# Manifest distant
# --------------------------------------------------------------------------
def _raw_base(repo, branch):
    return "https://raw.githubusercontent.com/%s/%s/" % (repo, branch)


def _fetch_manifest(repo, branch, path_prefix):
    """Le manifest est petit : on peut le charger entierement en RAM."""
    url = _raw_base(repo, branch) + path_prefix + "manifest.json"
    s, status, length, chunked = _open_url(url)
    try:
        if status in (301, 302, 303, 307, 308):
            s.close()
            url = _follow_location(url)
            s, status, length, chunked = _open_url(url)
        if status != 200:
            raise OSError("Manifest HTTP %d" % status)
        body = b""
        while True:
            block = s.read(CHUNK)
            if not block:
                break
            body += block
    finally:
        s.close()
    gc.collect()
    return json.loads(body)


# --------------------------------------------------------------------------
# Point d'entree
# --------------------------------------------------------------------------
def check_and_update(repo, branch="main", path_prefix="", force=False):
    """Verifie le manifest et applique les mises a jour si necessaire.

    Renvoie un dict :
        {"updated": bool, "version": str, "changed": [noms], "error": str|None}

    Ne redemarre PAS le Pico : c'est a l'appelant de le faire si updated.
    """
    result = {"updated": False, "version": None, "changed": [], "error": None}
    try:
        manifest = _fetch_manifest(repo, branch, path_prefix)
    except Exception as e:  # noqa: BLE001
        result["error"] = "manifest: %s" % e
        return result

    result["version"] = manifest.get("version")
    state = _load_state()
    local_files = state.get("files", {})

    if not force and manifest.get("version") == installed_version():
        return result  # deja a jour

    base = _raw_base(repo, branch) + path_prefix
    files = manifest.get("files", {})  # {"main.py": "sha256hex", ...}

    # 1) Telecharger uniquement les fichiers dont le hash differe -> .new
    downloaded = []
    try:
        for name, expected in files.items():
            if not force and local_files.get(name) == expected:
                continue  # inchange
            tmp = name + TMP_SUFFIX
            got = _stream_to_file(base + name, tmp)
            if got != expected:
                _safe_remove(tmp)
                raise OSError("Hash invalide pour %s" % name)
            downloaded.append(name)
            gc.collect()
    except Exception as e:  # noqa: BLE001
        for name in downloaded:
            _safe_remove(name + TMP_SUFFIX)
        result["error"] = str(e)
        return result

    # 2) Swap atomique des fichiers verifies
    import os
    for name in downloaded:
        try:
            os.remove(name)
        except OSError:
            pass
        os.rename(name + TMP_SUFFIX, name)

    # 3) Memoriser le nouvel etat
    state["version"] = manifest.get("version")
    state["files"] = files
    _save_state(state)

    result["updated"] = len(downloaded) > 0
    result["changed"] = downloaded
    gc.collect()
    return result


def _safe_remove(path):
    try:
        import os
        os.remove(path)
    except OSError:
        pass
