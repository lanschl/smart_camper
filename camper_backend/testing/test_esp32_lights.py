# Use absolute imports, assuming the script is run from the project root
from hardware.lights import LightController
from config import ESP32_LIGHT_CONFIG

print("--- Interactive ESP32 Light Controller Test ---")
print("This script MUST be run from the 'camper_backend' root directory, like this:")
print("python -m testing.test_esp32_lights")
print("\nEnter commands like 'deko 50', 'ambiente 100', or 'ceiling 0'.")
print("Type 'exit' to quit.")

# Initialize the real controller from our application
controller = LightController(ESP32_LIGHT_CONFIG['port'], ESP32_LIGHT_CONFIG['pins'])

if controller.is_mocked:
    print("\nERROR: Could not connect to ESP32. Exiting.")
    exit()

try:
    while True:
        cmd = input("> ").strip().lower()
        if cmd == 'exit':
            break
        
        try:
            parts = cmd.split()
            if len(parts) != 2:
                raise ValueError("Invalid format")
            
            light_id = parts[0]
            level = int(parts[1])
            
            controller.set_light_level(light_id, level)
            print(f"Set '{light_id}' to {level}%")

        except Exception as e:
            print(f"Invalid command. Please use format 'light_id level' (e.g., 'deko 50'). Error: {e}")

except KeyboardInterrupt:
    pass

finally:
    print("\nCleaning up and turning off lights...")
    controller.cleanup()
    print("Test finished.")