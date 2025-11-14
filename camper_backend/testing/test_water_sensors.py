# testing/test_water_sensors.py
import time
from gpiozero import DistanceSensor
# Config: 'fresh_1': {'trigger_pin': 5, 'echo_pin': 6}
TRIGGER_PIN = 5 # <-- CHANGE THESE PINS TO TEST EACH SENSOR
ECHO_PIN    = 6
print(f"--- Water Level Sensor Test (T{TRIGGER_PIN}/E{ECHO_PIN}) ---")
print("Press Ctrl+C to exit.")
try:
    while True:
        sensor = None
        try:
            sensor = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN)
            distance_cm = sensor.distance * 100
            print(f"Distance: {distance_cm:.1f} cm")
        finally:
            if sensor: sensor.close()
        time.sleep(2)
except KeyboardInterrupt:
    print("\nTest finished.")