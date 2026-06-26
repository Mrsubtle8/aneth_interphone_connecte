from machine import Pin
from time import ticks_ms
from config import DETECT_PIN, ANTI_DOUBLE_MS

detect = Pin(DETECT_PIN, Pin.IN, Pin.PULL_UP)

previous_state = detect.value()
last_detection = 0

def is_active():
    return detect.value() == 0

def check():
    global previous_state, last_detection

    state = detect.value()

    # Front descendant : 1 -> 0
    if previous_state == 1 and state == 0:
        now = ticks_ms()

        if now - last_detection > ANTI_DOUBLE_MS:
            last_detection = now
            previous_state = state
            return True

    previous_state = state
    return False