import socket
import gc
import machine
import config_store
import pushover
import relay
import interphone

SOUNDS = ["pushover","cosmic","bike","incoming","magic","siren","spacealarm","persistent","echo","updown","none"]

def url_decode(s):
    s = s.replace("+", " ")
    out = ""
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                out += chr(int(s[i+1:i+3], 16))
                i += 3
            except:
                out += s[i]
                i += 1
        else:
            out += s[i]
            i += 1
    return out

def html_escape(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def parse_form(body):
    data = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            data[url_decode(k)] = url_decode(v)
    return data

def send_response(conn, body, status="200 OK"):
    conn.send("HTTP/1.1 {}\r\n".format(status))
    conn.send("Content-Type: text/html\r\n")
    conn.send("Connection: close\r\n\r\n")
    conn.send(body)

def read_request(conn, first):
    headers = first.split("\r\n\r\n", 1)[0]
    body = ""
    if "\r\n\r\n" in first:
        body = first.split("\r\n\r\n", 1)[1]

    length = 0
    for line in headers.split("\r\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())

    while len(body) < length:
        body += conn.recv(512).decode()

    return body

def sound_options(current):
    html = ""
    for s in SOUNDS:
        sel = " selected" if s == current else ""
        html += '<option value="{}"{}>{}</option>'.format(s, sel, s)
    return html

def page(ip):
    cfg = config_store.load()
    state = "SONNERIE ACTIVE" if interphone.is_active() else "OK"

    return """<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interphone Pickles</title>
<style>
body{{font-family:-apple-system,Arial;margin:20px;background:#f4f4f4;color:#111}}
.card{{background:#fff;border-radius:14px;padding:16px;margin-bottom:14px}}
input,select,button{{width:100%;font-size:16px;padding:10px;margin:6px 0;box-sizing:border-box}}
button{{background:#111;color:white;border:0;border-radius:10px}}
small{{color:#666}}
</style>
</head>
<body>
<h1>Interphone Pickles</h1>

<div class="card">
<p><b>Etat :</b> {state}</p>
<p><b>IP :</b> {ip}</p>
</div>

<div class="card">
<h2>Actions</h2>
<p><a href="/test?password={pwd}"><button>Tester notification</button></a></p>
<p><a href="/open?password={pwd}"><button>Ouvrir porte</button></a></p>
<p><a href="/restart?password={pwd}"><button>Redemarrer Pico</button></a></p>
</div>

<div class="card">
<h2>Configuration</h2>
<form method="POST" action="/save">

<label>Mot de passe admin actuel</label>
<input name="admin_password" type="password">

<h3>Wi-Fi</h3>
<label>Nom Wi-Fi</label>
<input name="wifi_name" value="{wifi_name}">
<label>Mot de passe Wi-Fi</label>
<input name="wifi_password" value="{wifi_password}">

<h3>Pushover</h3>
<label>User Key</label>
<input name="pushover_user_key" value="{user_key}">
<label>API Token</label>
<input name="pushover_api_token" value="{api_token}">
<label>Message</label>
<input name="message" value="{message}">

<label>Sonnerie</label>
<select name="pushover_sound">{sound_options}</select>

<label>Priorite</label>
<select name="pushover_priority">
<option value="1" {p1}>Haute</option>
<option value="2" {p2}>Urgence avec retry</option>
</select>

<label>Retry secondes, minimum 30</label>
<input name="pushover_retry" value="{retry}">
<label>Expire secondes</label>
<input name="pushover_expire" value="{expire}">

<h3>Relais</h3>
<label>Duree impulsion ouverture, ms</label>
<input name="relay_pulse_ms" value="{relay_ms}">
<label>Relais active low</label>
<select name="relay_active_low">
<option value="false" {low_false}>false</option>
<option value="true" {low_true}>true</option>
</select>

<h3>Interphone</h3>
<label>Anti-double detection, ms</label>
<input name="anti_double_ms" value="{anti_ms}">

<h3>Admin</h3>
<label>Nouveau mot de passe admin</label>
<input name="web_password" value="{pwd}">

<button>Enregistrer et redemarrer</button>
</form>
</div>

<small>Branchement final : COM violet vers 9, NO marron vers 6.</small>
</body>
</html>""".format(
        state=state,
        ip=ip,
        pwd=html_escape(cfg["web_password"]),
        wifi_name=html_escape(cfg["wifi_name"]),
        wifi_password=html_escape(cfg["wifi_password"]),
        user_key=html_escape(cfg["pushover_user_key"]),
        api_token=html_escape(cfg["pushover_api_token"]),
        message=html_escape(cfg["message"]),
        sound_options=sound_options(cfg["pushover_sound"]),
        p1="selected" if int(cfg["pushover_priority"]) == 1 else "",
        p2="selected" if int(cfg["pushover_priority"]) == 2 else "",
        retry=cfg["pushover_retry"],
        expire=cfg["pushover_expire"],
        relay_ms=cfg["relay_pulse_ms"],
        anti_ms=cfg["anti_double_ms"],
        low_true="selected" if cfg["relay_active_low"] else "",
        low_false="selected" if not cfg["relay_active_low"] else ""
    )

def start():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    sock.listen(1)
    sock.settimeout(0.05)
    return sock

def step(sock, ip):
    conn = None
    try:
        conn, addr = sock.accept()
        first = conn.recv(1024).decode()
        first_line = first.split("\r\n")[0]
        method = first_line.split(" ")[0]
        path = first_line.split(" ")[1]

        cfg = config_store.load()
        pwd = cfg["web_password"]

        if method == "GET" and path == "/":
            send_response(conn, page(ip))

        elif method == "GET" and path.startswith("/test?password=" + pwd):
            send_response(conn, "<html><body>Test envoye</body></html>")
            conn.close()
            conn = None
            gc.collect()
            pushover.send("Test notification interphone.")

        elif method == "GET" and path.startswith("/open?password=" + pwd):
            relay.pulse()
            send_response(conn, "<html><body>Porte ouverte</body></html>")

        elif method == "GET" and path.startswith("/restart?password=" + pwd):
            send_response(conn, "<html><body>Redemarrage...</body></html>")
            conn.close()
            machine.reset()

        elif method == "POST" and path == "/save":
            body = read_request(conn, first)
            form = parse_form(body)

            if form.get("admin_password", "") != pwd:
                send_response(conn, "<html><body>Mot de passe incorrect</body></html>", "403 Forbidden")
            else:
                cfg["wifi_name"] = form.get("wifi_name", cfg["wifi_name"])
                cfg["wifi_password"] = form.get("wifi_password", cfg["wifi_password"])
                cfg["pushover_user_key"] = form.get("pushover_user_key", cfg["pushover_user_key"])
                cfg["pushover_api_token"] = form.get("pushover_api_token", cfg["pushover_api_token"])
                cfg["message"] = form.get("message", cfg["message"])
                cfg["pushover_sound"] = form.get("pushover_sound", cfg["pushover_sound"])
                cfg["pushover_priority"] = int(form.get("pushover_priority", cfg["pushover_priority"]))
                cfg["pushover_retry"] = max(30, int(form.get("pushover_retry", cfg["pushover_retry"])))
                cfg["pushover_expire"] = int(form.get("pushover_expire", cfg["pushover_expire"]))
                cfg["relay_pulse_ms"] = int(form.get("relay_pulse_ms", cfg["relay_pulse_ms"]))
                cfg["anti_double_ms"] = int(form.get("anti_double_ms", cfg["anti_double_ms"]))
                cfg["relay_active_low"] = form.get("relay_active_low", "false") == "true"
                cfg["web_password"] = form.get("web_password", cfg["web_password"])

                config_store.save(cfg)

                send_response(conn, "<html><body>Config sauvegardee. Redemarrage...</body></html>")
                conn.close()
                machine.reset()

        else:
            send_response(conn, "<html><body>Refuse</body></html>", "403 Forbidden")

    except OSError:
        pass
    except Exception as e:
        print("Erreur web:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
        gc.collect()