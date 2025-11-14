import lgpio
from typing import Dict

class LightController:
    """
    Manages dimmable LED lights using Hardware PWM on GPIO pins.
    """
    def __init__(self, pin_config: Dict[str, int]):
        """
        Initializes the light controller.
        :param pin_config: A dictionary mapping light IDs to BCM GPIO pin numbers.
        """
        print("Initializing Light Controller...")
        self.pin_config = pin_config
        self.chip_handle = -1
        self.PWM_FREQUENCY = 500  # 500 Hz is a good frequency for LEDs to avoid flicker

        try:
            self.chip_handle = lgpio.gpiochip_open(0)
            
            for light_id, pin in self.pin_config.items():
                # We don't "claim" the pin, we just start the PWM signal on it.
                # The lgpio library handles the setup.
                print(f"  - Setting up PWM on GPIO {pin} for '{light_id}'")
                
                # Start with lights off (0% duty cycle)
                self.set_light_level(light_id, 0)
                
            print("Light Controller initialized successfully.")

        except lgpio.error as e:
            print(f"Error initializing GPIO for PWM: {e}")
            print("GPIO operations will be mocked. Hardware will not be controlled.")
            self.chip_handle = -1

    def set_light_level(self, light_id: str, level: int):
        """
        Sets the brightness level of a specific light.
        :param light_id: The ID of the light (e.g., 'deko').
        :param level: The brightness level from 0 to 100.
        """
        if light_id not in self.pin_config:
            print(f"Warning: Unknown light_id '{light_id}'")
            return

        pin = self.pin_config[light_id]
        
        # Clamp the level to a safe 0-100 range
        duty_cycle = max(0, min(100, level))
        
        print(f"Setting light '{light_id}' (GPIO {pin}) to {duty_cycle}% brightness")

        if self.chip_handle < 0:
            print("  (Mocked call, no hardware action)")
            return
            
        try:
            # lgpio.tx_pwm(chip_handle, gpio_pin, frequency, duty_cycle_percent)
            lgpio.tx_pwm(self.chip_handle, pin, self.PWM_FREQUENCY, duty_cycle)
        except lgpio.error as e:
            print(f"Error setting PWM on GPIO {pin}: {e}")

    def cleanup(self):
        """
        Turns off all lights and stops PWM signals.
        """
        if self.chip_handle < 0:
            return
            
        print("Cleaning up light controller (turning off all lights)...")
        for light_id, pin in self.pin_config.items():
            try:
                # Set duty cycle to 0 before stopping
                lgpio.tx_pwm(self.chip_handle, pin, self.PWM_FREQUENCY, 0)
            except lgpio.error:
                pass # Ignore errors on cleanup
        
        # The lgpio daemon will handle stopping the PWM when the chip is closed.
        # lgpio.gpiochip_close(self.chip_handle) is handled by the valve controller.
        # If this were a standalone app, you'd close the chip handle here.
        print("Light cleanup complete.")