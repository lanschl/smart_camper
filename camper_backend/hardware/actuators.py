# hardware/actuators.py

import time
import threading
from gpiozero import DigitalOutputDevice
from gpiozero.exc import GPIOZeroError
from typing import Dict

class ActuatorController:
    """
    Manages momentary pulse actuators (e.g., central locking motors)
    connected via MOSFETs, using a timed, non-blocking pulse.
    """
    def __init__(self, pin_config: Dict):
        print("Initializing Actuator Controller (using gpiozero)...")
        self.pin_config = pin_config
        self.devices = {}
        self.is_mocked = False

        try:
            for actuator_id, pins in self.pin_config.items():
                lock_pin = pins['lock_pin']
                unlock_pin = pins['unlock_pin']
                
                self.devices[actuator_id] = {
                    'lock': DigitalOutputDevice(lock_pin, active_high=True, initial_value=False),
                    'unlock': DigitalOutputDevice(unlock_pin, active_high=True, initial_value=False)
                }
                print(f"  - Configured '{actuator_id}' with LOCK pin {lock_pin} and UNLOCK pin {unlock_pin}")
            print("Actuator Controller initialized successfully.")

        except GPIOZeroError as e:
            print(f"Error initializing gpiozero for actuators: {e}")
            self.is_mocked = True

    def _fire_pulse(self, device: DigitalOutputDevice, duration: float):
        """Private method to run in a separate thread."""
        device.on()
        time.sleep(duration)
        device.off()
        print(f"Pulse finished on pin {device.pin}.")

    def trigger_actuator(self, actuator_id: str, action: str, duration: float = 1.0):
        """
        Fires a non-blocking pulse to the specified actuator action pin.
        :param actuator_id: The ID of the actuator (e.g., 'drawers').
        :param action: The action to perform ('lock' or 'unlock').
        :param duration: The duration of the pulse in seconds.
        """
        if actuator_id not in self.devices:
            print(f"Warning: Unknown actuator_id '{actuator_id}'")
            return

        if action not in self.devices[actuator_id]:
            print(f"Warning: Unknown action '{action}' for actuator '{actuator_id}'")
            return
            
        print(f"Triggering '{action}' pulse for '{actuator_id}' for {duration}s...")
        
        if self.is_mocked:
            print("  (Mocked call, no hardware action)")
            return

        device_to_fire = self.devices[actuator_id][action]
        
        # Create and start a thread to handle the pulse.
        # This is CRUCIAL to prevent the whole server from freezing for 1 second.
        pulse_thread = threading.Thread(
            target=self._fire_pulse, args=(device_to_fire, duration)
        )
        pulse_thread.start()

    def cleanup(self):
        print("Cleaning up actuator controller...")
        if not self.is_mocked:
            for device_set in self.devices.values():
                device_set['lock'].close()
                device_set['unlock'].close()
        print("Actuator cleanup complete.")