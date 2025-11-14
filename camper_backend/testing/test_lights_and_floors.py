# testing/test_lights_and_floors.py
from gpiozero import PWMLED
from time import sleep
# Config: {'deko': 12, 'ambiente': 13, 'ceiling': 14, 'floor_heat': 16}
PIN = 12 # <-- CHANGE THIS PIN NUMBER TO TEST EACH LIGHT/FLOOR
print(f"--- PWM Device Test on GPIO {PIN} ---")
print("Press Ctrl+C to exit.")
try:
    device = PWMLED(PIN, frequency=100)
    while True:
        level_str = input("Enter brightness/level (0 to 100): ")
        if not level_str: continue
        level = int(level_str)
        pwm_value = max(0, min(100, level)) / 100.0
        device.value = pwm_value
        print(f"Set to {level}%")
except KeyboardInterrupt:
    device.off()
    print("\nTest finished.")