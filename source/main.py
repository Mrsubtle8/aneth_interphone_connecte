from time import sleep
from machine import Pin

import wifi_manager
import pushover
import relay
import interphone
import web
import telegram

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

    telegram.poll()

    if interphone.check():
        print(">>> SONNERIE DETECTEE <<<")
        pushover.send(ip=ip)
        telegram.notify("Quelqu'un sonne a la porte")

    led.value(1 if interphone.is_active() else 0)

    sleep(0.02)
