# hardware/esp32_light_controller.py
import serial
import logging
import threading
from typing import Dict

class LightController:
    """
    Manages dimmable lights via a serial connection to an ESP32 PWM controller.
    """
    def __init__(self, port: str, pin_config: Dict[str, int]):
        logging.info("Initializing ESP32 Light Controller...")
        self.pin_config = pin_config
        self.port = port
        self.ser = None
        self.is_mocked = False
        self.lock = threading.Lock() # To prevent concurrent serial writes

        try:
            self.ser = serial.Serial(self.port, 115200, timeout=1)
            logging.info(f"Successfully connected to ESP32 on {self.port}")
        except serial.SerialException as e:
            logging.error(f"Failed to connect to ESP32 on {self.port}: {e}")
            self.is_mocked = True

    def set_light_level(self, light_id: str, level: int):
        """
        Sets the brightness level of a specific light.
        :param light_id: The ID of the light (e.g., 'deko').
        :param level: The brightness level from 0 to 100.
        """
        if self.is_mocked:
            logging.warning(f"  (Mocked call) Set '{light_id}' to {level}%")
            return

        if light_id not in self.pin_config:
            logging.warning(f"Warning: Unknown light_id '{light_id}'")
            return

        # Convert 0-100 level to 0-1023 duty cycle for the ESP32
        duty_10bit = int(max(0, min(100, level)) / 100.0 * 1023)
        
        # The command format is "light_id,duty_value\n"
        command = f"{light_id},{duty_10bit}\n"
        
        # Use a lock to ensure only one thread writes to serial at a time
        with self.lock:
            logging.info(f"Sending to ESP32: '{command.strip()}'")
            self.ser.write(command.encode('utf-8'))

    def cleanup(self):
        """Turns off all lights and closes the serial connection."""
        logging.info("Cleaning up ESP32 light controller...")
        if self.ser:
            for light_id in self.pin_config.keys():
                self.set_light_level(light_id, 0) # Turn off light
            self.ser.close()
            logging.info("ESP32 serial connection closed.")