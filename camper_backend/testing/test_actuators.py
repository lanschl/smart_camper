# testing/test_actuators.py
from gpiozero import DigitalOutputDevice
import time
LOCK_PIN = 20
UNLOCK_PIN = 21
print("--- Drawer Lock Actuator Test ---")
lock = DigitalOutputDevice(LOCK_PIN)
unlock = DigitalOutputDevice(UNLOCK_PIN)
try:
    while True:
        input("Press Enter to FIRE LOCK pulse for 1 second...")
        lock.on()
        print("LOCK ON")
        time.sleep(1)
        lock.off()
        print("LOCK OFF")
        input("Press Enter to FIRE UNLOCK pulse for 1 second...")
        unlock.on()
        print("UNLOCK ON")
        time.sleep(1)
        unlock.off()
        print("UNLOCK OFF")
except KeyboardInterrupt:
    print("\nTest finished.")