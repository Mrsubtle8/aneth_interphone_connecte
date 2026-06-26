import socket
import gc
import machine
import config_store
import pushover
import relay
import interphone
import ota

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

def js_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def parse_form(body):
    data = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            data[url_decode(k)] = url_decode(v)
    return data

def send_response(conn, body, status="200 OK"):
    conn.send("HTTP/1.1 {}\r\n".format(status))
    conn.send("Content-Type: text/html; charset=utf-8\r\n")
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
        chunk = conn.recv(512)
        if not chunk:
            break
        body += chunk.decode()

    return body

def sound_options(current):
    html = ""
    for s in SOUNDS:
        sel = " selected" if s == current else ""
        html += '<option value="{}"{}>{}</option>'.format(s, sel, s)
    return html


# JavaScript de la page : tout passe par fetch() + toast, aucune navigation.
# __PWD__ est remplace par le mot de passe admin (comme l'ancien ?password=...).
SCRIPT = """
<script>
var PWD = __PWD__;
var tt;
function toast(msg, ok){
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = (ok === false) ? '#b00020' : '#222';
  t.style.opacity = 1;
  clearTimeout(tt);
  tt = setTimeout(function(){ t.style.opacity = 0; }, 4000);
}
function action(path, label){
  toast(label + '...');
  fetch(path, {cache:'no-store'})
    .then(function(r){ return r.text(); })
    .then(function(t){ toast(t || 'OK'); })
    .catch(function(){ toast('Erreur reseau', false); });
}
function doTest(){ action('/test?password=' + PWD, 'Envoi du test'); }
function doOpen(){ action('/open?password=' + PWD, 'Ouverture'); }
function doUpdate(){
  toast('Recherche de mise a jour...');
  fetch('/update?password=' + PWD, {cache:'no-store'})
    .then(function(r){ return r.text(); })
    .then(function(t){
      toast(t);
      if (t.indexOf('Mis a jour') === 0){ waitReboot(); }
    })
    .catch(function(){ waitReboot(); });
}
function doRestart(){
  if (!confirm('Redemarrer le Pico ?')) return;
  fetch('/restart?password=' + PWD, {cache:'no-store'}).catch(function(){});
  waitReboot();
}
function waitReboot(){
  toast('Redemarrage... reconnexion en cours');
  var tries = 0;
  var iv = setInterval(function(){
    tries++;
    fetch('/', {cache:'no-store'})
      .then(function(){ clearInterval(iv); location.reload(); })
      .catch(function(){ if (tries > 40){ clearInterval(iv); toast('Toujours hors ligne', false); } });
  }, 1500);
}
function doSave(e){
  e.preventDefault();
  var f = document.getElementById('cfg');
  var body = new URLSearchParams(new FormData(f)).toString();
  toast('Enregistrement...');
  fetch('/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: body
  })
    .then(function(r){ return r.text(); })
    .then(function(t){ toast(t); })
    .catch(function(){ toast('Erreur reseau', false); });
  return false;
}
</script>
"""

def page(ip):
    cfg = config_store.load()
    state = "SONNERIE ACTIVE" if interphone.is_active() else "OK"

    try:
        fw_version = ota._load_state().get("version", "0.0.0")
    except Exception:
        fw_version = "0.0.0"

    html = """<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interphone Pickles</title>
<style>
body{{font-family:-apple-system,Arial;margin:20px;background:#f4f4f4;color:#111}}
.card{{background:#fff;border-radius:14px;padding:16px;margin-bottom:14px}}
input,select,button{{width:100%;font-size:16px;padding:10px;margin:6px 0;box-sizing:border-box}}
button{{background:#111;color:white;border:0;border-radius:10px;cursor:pointer}}
button.alt{{background:#555}}
small{{color:#666}}
#toast{{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#222;color:#fff;padding:12px 18px;border-radius:10px;opacity:0;transition:opacity .3s;max-width:90%;text-align:center;z-index:99}}
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
<button type="button" onclick="doTest()">Tester notification</button>
<button type="button" onclick="doOpen()">Ouvrir porte</button>
<button type="button" onclick="doUpdate()">Mettre a jour le firmware</button>
<button type="button" class="alt" onclick="doRestart()">Redemarrer Pico</button>
<p><small>Version installee : {fw_version}</small></p>
</div>

<div class="card">
<h2>Configuration</h2>
<form id="cfg" onsubmit="return doSave(event)">

<label>Mot de passe admin actuel (requis pour enregistrer)</label>
<input name="admin_password" type="password">

<h3>Wi-Fi</h3>
<label>Nom Wi-Fi</label>
<input name="wifi_name" value="{wifi_name}">
<label>Mot de passe Wi-Fi</label>
<input name="wifi_password" type="password" placeholder="(inchange)">

<h3>Pushover</h3>
<label>User Key</label>
<input name="pushover_user_key" type="password" placeholder="(inchange)">
<label>API Token</label>
<input name="pushover_api_token" type="password" placeholder="(inchange)">
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

<h3>Mise a jour (OTA)</h3>
<label>Depot GitHub</label>
<input name="ota_repo" value="{ota_repo}">
<label>Branche</label>
<input name="ota_branch" value="{ota_branch}">
<label>Sous-dossier dans le depot</label>
<input name="ota_path" value="{ota_path}">

<h3>Admin</h3>
<label>Nouveau mot de passe admin</label>
<input name="web_password" type="password" placeholder="(laisser vide = inchange)">

<button>Enregistrer</button>
</form>
<small>Wi-Fi, broches, relais et anti-double s'appliquent au redemarrage. Le message et la sonnerie sont immediats.</small>
</div>

<small>Branchement final : COM violet vers 9, NO marron vers 6.</small>

<div id="toast"></div>
{script}
</body>
</html>""".format(
        state=state,
        ip=ip,
        fw_version=html_escape(fw_version),
        ota_repo=html_escape(cfg["ota_repo"]),
        ota_branch=html_escape(cfg["ota_branch"]),
        ota_path=html_escape(cfg["ota_path"]),
        wifi_name=html_escape(cfg["wifi_name"]),
        message=html_escape(cfg["message"]),
        sound_options=sound_options(cfg["pushover_sound"]),
        p1="selected" if int(cfg["pushover_priority"]) == 1 else "",
        p2="selected" if int(cfg["pushover_priority"]) == 2 else "",
        retry=cfg["pushover_retry"],
        expire=cfg["pushover_expire"],
        relay_ms=cfg["relay_pulse_ms"],
        anti_ms=cfg["anti_double_ms"],
        low_true="selected" if cfg["relay_active_low"] else "",
        low_false="selected" if not cfg["relay_active_low"] else "",
        script=SCRIPT.replace("__PWD__", js_str(cfg["web_password"]))
    )
    return html

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
        # La socket acceptee herite du timeout 0.05s de la socket d'ecoute :
        # trop court pour lire le corps d'un POST (arrive en 2e segment TCP).
        conn.settimeout(2.0)
        first = conn.recv(1024).decode()
        first_line = first.split("\r\n")[0]
        method = first_line.split(" ")[0]
        path = first_line.split(" ")[1]

        cfg = config_store.load()
        pwd = cfg["web_password"]

        if method == "GET" and path == "/":
            send_response(conn, page(ip))

        elif method == "GET" and path == "/favicon.ico":
            send_response(conn, "", "204 No Content")

        elif method == "GET" and path.startswith("/test?password=" + pwd):
            send_response(conn, "Notification de test envoyee")
            conn.close()
            conn = None
            gc.collect()
            pushover.send("Test notification interphone.")

        elif method == "GET" and path.startswith("/open?password=" + pwd):
            relay.pulse()
            send_response(conn, "Porte ouverte")

        elif method == "GET" and path.startswith("/update?password=" + pwd):
            gc.collect()
            res = ota.check_and_update(
                cfg["ota_repo"], cfg["ota_branch"], cfg["ota_path"]
            )
            if res["error"]:
                send_response(conn, "Erreur OTA : " + res["error"])
            elif res["updated"]:
                send_response(
                    conn,
                    "Mis a jour vers " + str(res["version"]) +
                    " (" + ", ".join(res["changed"]) + ")"
                )
                conn.close()
                conn = None
                machine.reset()
            else:
                send_response(conn, "Deja a jour (version " + str(res["version"]) + ")")

        elif method == "GET" and path.startswith("/restart?password=" + pwd):
            send_response(conn, "Redemarrage")
            conn.close()
            conn = None
            machine.reset()

        elif method == "POST" and path == "/save":
            body = read_request(conn, first)
            form = parse_form(body)

            if form.get("admin_password", "") != pwd:
                send_response(conn, "Mot de passe admin incorrect", "403 Forbidden")
            else:
                cfg["wifi_name"] = form.get("wifi_name", cfg["wifi_name"])
                cfg["message"] = form.get("message", cfg["message"])
                cfg["pushover_sound"] = form.get("pushover_sound", cfg["pushover_sound"])
                cfg["pushover_priority"] = int(form.get("pushover_priority", cfg["pushover_priority"]))
                cfg["pushover_retry"] = max(30, int(form.get("pushover_retry", cfg["pushover_retry"])))
                cfg["pushover_expire"] = int(form.get("pushover_expire", cfg["pushover_expire"]))
                cfg["relay_pulse_ms"] = int(form.get("relay_pulse_ms", cfg["relay_pulse_ms"]))
                cfg["anti_double_ms"] = int(form.get("anti_double_ms", cfg["anti_double_ms"]))
                cfg["relay_active_low"] = form.get("relay_active_low", "false") == "true"
                cfg["ota_repo"] = form.get("ota_repo", cfg["ota_repo"])
                cfg["ota_branch"] = form.get("ota_branch", cfg["ota_branch"])
                cfg["ota_path"] = form.get("ota_path", cfg["ota_path"])

                # Champs sensibles : on ne remplace que si l'utilisateur a saisi
                # quelque chose (sinon on garde la valeur existante).
                if form.get("wifi_password"):
                    cfg["wifi_password"] = form["wifi_password"]
                if form.get("pushover_user_key"):
                    cfg["pushover_user_key"] = form["pushover_user_key"]
                if form.get("pushover_api_token"):
                    cfg["pushover_api_token"] = form["pushover_api_token"]
                if form.get("web_password"):
                    cfg["web_password"] = form["web_password"]

                config_store.save(cfg)
                send_response(conn, "Enregistre. Redemarrer pour appliquer Wi-Fi / broches / relais.")

        else:
            send_response(conn, "Refuse", "403 Forbidden")

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
