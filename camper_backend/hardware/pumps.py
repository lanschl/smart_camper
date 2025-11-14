# hardware/pumps.py

from gpiozero import DigitalOutputDevice
from gpiozero.exc import GPIOZeroError
from typing import Dict

class PumpController:
    """
    Manages simple on/off water pumps connected via MOSFETs using gpiozero.
    """
    def __init__(self, pin_config: Dict[str, int]):
        """
        Initializes the pump controller.
        :param pin_config: A dictionary mapping pump IDs to BCM GPIO pin numbers.
        """
        print("Initializing Pump Controller (using gpiozero)...")
        self.pin_config = pin_config
        self.devices: Dict[str, DigitalOutputDevice] = {}
        self.is_mocked = False

        try:
            for pump_id, pin in self.pin_config.items():
                # active_high=True is standard for these MOSFET boards (3.3V signal = ON)
                # initial_value=False ensures pumps are OFF at startup
                self.devices[pump_id] = DigitalOutputDevice(
                    pin, active_high=True, initial_value=False
                )
                print(f"  - Configured GPIO {pin} for '{pump_id}'")
            print("Pump Controller initialized successfully.")

        except GPIOZeroError as e:
            print(f"Error initializing gpiozero: {e}")
            print("GPIO operations will be mocked. Hardware will not be controlled.")
            self.is_mocked = True

    def set_pump_state(self, pump_id: str, is_on: bool):
        """
        Sets the state of a specific pump.
        :param pump_id: The ID of the pump (e.g., 'fresh_pump').
        :param is_on: True to turn the pump ON, False to turn it OFF.
        """
        if pump_id not in self.pin_config:
            print(f"Warning: Unknown pump_id '{pump_id}'")
            return

        state_str = "ON" if is_on else "OFF"
        pin = self.pin_config[pump_id]
        print(f"Setting pump '{pump_id}' (GPIO {pin}) to {state_str}")

        if self.is_mocked:
            print("  (Mocked call, no hardware action)")
            return

        device = self.devices[pump_id]
        if is_on:
            device.on()
        else:
            device.off()

    def cleanup(self):
        """
        Turns off all pumps and releases GPIO resources.
        """
        print("Cleaning up pump controller (turning off all pumps)...")
        if not self.is_mocked:
            for device in self.devices.values():
                device.off()
                device.close()
        print("Pump cleanup complete.")