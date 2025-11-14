# hardware/valves.py

import lgpio
import time
from typing import Dict

class ValveController:
    """
    Manages the state of solenoid valves connected to GPIO pins via relays.
    Note: Assumes relays are ACTIVE LOW (a LOW signal turns the relay ON).
          If your relay is ACTIVE HIGH, change lgpio.LOW to lgpio.HIGH in the 'on' state.
    """
    def __init__(self, pin_config: Dict[str, int]):
        """
        Initializes the valve controller.
        :param pin_config: A dictionary mapping valve IDs to BCM GPIO pin numbers.
        """
        print("Initializing Valve Controller...")
        self.pin_config = pin_config
        self.chip_handle = -1
        self.valve_handles = {}

        try:
            # Get a handle to the primary GPIO chip
            self.chip_handle = lgpio.gpiochip_open(0)

            for valve_id, pin in self.pin_config.items():
                # Claim the GPIO pin for output
                lgpio.gpio_claim_output(self.chip_handle, pin)
                self.valve_handles[valve_id] = pin
                print(f"  - Claimed GPIO {pin} for '{valve_id}'")
                
                # IMPORTANT: Set initial state to OFF
                # Relays are often "active low", meaning a LOW signal turns them ON.
                # So, to ensure they are OFF, we set the pin HIGH.
                self.set_valve_state(valve_id, False)

            print("Valve Controller initialized successfully.")

        except lgpio.error as e:
            print(f"Error initializing GPIO: {e}")
            print("GPIO operations will be mocked. Hardware will not be controlled.")
            self.chip_handle = -1 # Mark as failed
            
    def set_valve_state(self, valve_id: str, is_on: bool):
        """
        Sets the state of a specific valve.
        :param valve_id: The ID of the valve (e.g., 'gray_drain').
        :param is_on: True to open the valve (turn relay ON), False to close.
        """
        if valve_id not in self.pin_config:
            print(f"Warning: Unknown valve_id '{valve_id}'")
            return

        pin = self.pin_config[valve_id]
        state_str = "ON (OPEN)" if is_on else "OFF (CLOSED)"
        print(f"Setting valve '{valve_id}' (GPIO {pin}) to {state_str}")

        # If GPIO initialization failed, don't try to control hardware
        if self.chip_handle < 0:
            print("  (Mocked call, no hardware action)")
            return

        try:
            # Active Low Logic:
            # To turn the relay ON, we write a LOW signal.
            # To turn the relay OFF, we write a HIGH signal.
            level = lgpio.LOW if is_on else lgpio.HIGH
            lgpio.gpio_write(self.chip_handle, pin, level)
        except lgpio.error as e:
            print(f"Error writing to GPIO {pin}: {e}")

    def cleanup(self):
        """
        Releases all claimed GPIO pins. Call this on application exit.
        """
        if self.chip_handle < 0:
            return
            
        print("Cleaning up GPIO pins...")
        for valve_id, pin in self.pin_config.items():
            # Set pin back to a safe state (OFF) before freeing
            self.set_valve_state(valve_id, False)
            time.sleep(0.1) # Small delay
        
        lgpio.gpiochip_close(self.chip_handle)
        print("GPIO cleanup complete.")