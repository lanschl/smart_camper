# hardware/pwm_devices.py

from gpiozero import PWMLED
from gpiozero.exc import GPIOZeroError
from typing import Dict

class PWMDeviceController:
    """
    Manages PWM-controlled devices (dimmable lights, heaters) using gpiozero.
    """
    def __init__(self, pin_config: Dict[str, int]):
        print("Initializing PWM Device Controller (using gpiozero)...")
        self.pin_config = pin_config
        self.devices: Dict[str, PWMLED] = {}
        self.is_mocked = False
        self.PWM_FREQUENCY = 100 # 100 Hz is good for heating elements

        try:
            for device_id, pin in self.pin_config.items():
                # PWMLED is the gpiozero object for PWM control.
                # initial_value=0 ensures it's off at startup.
                self.devices[device_id] = PWMLED(
                    pin, frequency=self.PWM_FREQUENCY, initial_value=0
                )
                print(f"  - Configured PWM on GPIO {pin} for device '{device_id}'")
            print("PWM Device Controller initialized successfully.")

        except GPIOZeroError as e:
            print(f"Error initializing gpiozero for PWM: {e}")
            self.is_mocked = True
    
    def set_level(self, device_id: str, level: int):
        if device_id not in self.devices:
            print(f"Warning: Unknown PWM device_id '{device_id}'")
            return
        
        # gpiozero's PWM value is a float from 0.0 to 1.0
        # The UI gives us an integer from 0 to 100.
        pwm_value = max(0, min(100, level)) / 100.0
        
        pin = self.pin_config[device_id]
        print(f"Setting PWM device '{device_id}' (GPIO {pin}) to {level}%")

        if self.is_mocked:
            print("  (Mocked call, no hardware action)")
            return
            
        self.devices[device_id].value = pwm_value

    def cleanup(self):
        print("Cleaning up PWM device controller...")
        if not self.is_mocked:
            for device in self.devices.values():
                device.off()
                device.close()
        print("PWM device cleanup complete.")