# testing/test_ds18b20_sensors.py
# This script discovers all connected DS18B20 sensors and prints their unique IDs.
import time
from w1thermsensor import W1ThermSensor
print("--- DS18B20 Temperature Sensor Discovery Tool ---")
try:
    sensors = W1ThermSensor.get_available_sensors()
    if not sensors:
        print("\nERROR: No sensors found! Check wiring and /boot/firmware/config.txt.")
    else:
        print(f"\nFound {len(sensors)} sensor(s). Starting live readings...")
        while True:
            for sensor in sensors:
                print(f"  - Sensor ID: {sensor.id}   Temperature: {sensor.get_temperature():.2f} °C")
            print("-" * 60)
            time.sleep(2)
except KeyboardInterrupt:
    print("\nTest stopped.")
except Exception as e:
    print(f"\nAn error occurred: {e}")
    