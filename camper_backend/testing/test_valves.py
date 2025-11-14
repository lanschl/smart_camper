# testing/test_valves.py
import lgpio
import time
PINS = [17, 27, 22] # Gray, Fresh Winter, Shower
print("--- Valve (Relay) Test ---")
print(f"Will toggle pins {PINS} every 2 seconds. Assumes ACTIVE LOW.")
print("Press Ctrl+C to exit.")
try:
    h = lgpio.gpiochip_open(0)
    for pin in PINS:
        lgpio.gpio_claim_output(h, pin)
        lgpio.gpio_write(h, pin, 1) # Start OFF
    while True:
        print("Turning valves ON (sending LOW)...")
        for pin in PINS: lgpio.gpio_write(h, pin, 0)
        time.sleep(2)
        print("Turning valves OFF (sending HIGH)...")
        for pin in PINS: lgpio.gpio_write(h, pin, 1)
        time.sleep(2)
except KeyboardInterrupt:
    print("\nCleaning up...")
    for pin in PINS: lgpio.gpio_write(h, pin, 1)
    lgpio.gpiochip_close(h)
    print("Done.")

    