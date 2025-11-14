# testing/test_pumps_and_switches.py
from gpiozero import DigitalOutputDevice
from time import sleep
# Config: {'fresh_pump': 23, 'hot_pump': 24, 'boiler_heat': 25}
PIN = 23 # <-- CHANGE THIS PIN NUMBER TO TEST EACH PUMP/SWITCH
print(f"--- Pump/Switch (MOSFET/SSR) Test on GPIO {PIN} ---")
print("Press Ctrl+C to exit.")
try:
    device = DigitalOutputDevice(PIN, active_high=True, initial_value=False)
    while True:
        print("Turning device ON...")
        device.on()
        sleep(3)
        print("Turning device OFF...")
        device.off()
        sleep(3)
except KeyboardInterrupt:
    device.off()
    print("\nTest finished.")