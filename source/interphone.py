from machine import Pin
from time import ticks_ms, ticks_diff
import config_store

_cfg = config_store.load()
ANTI_DOUBLE_MS = _cfg["anti_double_ms"]

detect = Pin(_cfg["detect_pin"], Pin.IN, Pin.PULL_UP)

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

        if ticks_diff(now, last_detection) > ANTI_DOUBLE_MS:
            last_detection = now
            previous_state = state
            return True

    previous_state = state
    return False
