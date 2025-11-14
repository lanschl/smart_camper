# hardware/switches.py

from gpiozero import DigitalOutputDevice
from gpiozero.exc import GPIOZeroError
from typing import Dict

class SwitchController:
    """
    Manages simple on/off devices (relays, SSRs) using gpiozero.
    """
    def __init__(self, pin_config: Dict[str, int]):
        print("Initializing Generic Switch Controller (using gpiozero)...")
        self.pin_config = pin_config
        self.devices: Dict[str, DigitalOutputDevice] = {}
        self.is_mocked = False

        try:
            for device_id, pin in self.pin_config.items():
                self.devices[device_id] = DigitalOutputDevice(
                    pin, active_high=True, initial_value=False
                )
                print(f"  - Configured GPIO {pin} for switch '{device_id}'")
            print("Switch Controller initialized successfully.")

        except GPIOZeroError as e:
            print(f"Error initializing gpiozero for switches: {e}")
            self.is_mocked = True

    def set_state(self, device_id: str, is_on: bool):
        if device_id not in self.devices:
            print(f"Warning: Unknown switch_id '{device_id}'")
            return

        state_str = "ON" if is_on else "OFF"
        pin = self.pin_config[device_id]
        print(f"Setting switch '{device_id}' (GPIO {pin}) to {state_str}")

        if self.is_mocked:
            print("  (Mocked call, no hardware action)")
            return

        device = self.devices[device_id]
        if is_on:
            device.on()
        else:
            device.off()

    def cleanup(self):
        print("Cleaning up switch controller...")
        if not self.is_mocked:
            for device in self.devices.values():
                device.off()
                device.close()
        print("Switch cleanup complete.")