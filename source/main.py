from time import sleep
from machine import Pin

from config import MESSAGE
import wifi_manager
import pushover
import relay
import interphone
import web

led = Pin("LED", Pin.OUT)

print("MAIN.PY DEMARRE")

wifi = wifi_manager.connect()
ip = wifi.ifconfig()[0]

sock = web.start()

print("===================================")
print(" Interphone Pickles V2 pret")
print(" Page web : http://" + ip)
print("===================================")

while True:
    if not wifi.isconnected():
        print("Wi-Fi perdu, reconnexion...")
        wifi = wifi_manager.connect()
        ip = wifi.ifconfig()[0]

    web.step(sock, ip)

    if interphone.check():
        print(">>> SONNERIE DETECTEE <<<")
        pushover.send(MESSAGE)

    led.value(1 if interphone.is_active() else 0)

    sleep(0.02)