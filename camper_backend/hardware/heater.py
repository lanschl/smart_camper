# hardware/heater.py
import time
import logging
from .autotherm_heater_control.autoterm_heater import AutotermPassthrough, status_text
from typing import Dict, Any, Optional

# Map the library's integer status codes to the strings our frontend uses
STATUS_MAP = {
    0: 'off', 1: 'starting', 2: 'warming_up', 3: 'running', 4: 'shutting_down'
}
# Map our frontend mode strings to the library's integer codes
MODE_MAP = {
    'temperature': 2, # Corresponds to "By controller temperature"
    'power': 4,       # Corresponds to "By power"
}

class HeaterController:
    """
    A controller that correctly wraps the autoterm_heater library, using its
    internal logic and state.
    """
    def __init__(self, serial_num: str, log_path: str):
        logging.info("Initializing Autoterm Heater Controller...")
        self.is_mocked = False
        try:
            self.heater = AutotermPassthrough(
                serial_num=serial_num,
                log_path=log_path,
                log_level=logging.INFO
            )
            logging.info("Heater connection successfully initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize heater controller: {e}", exc_info=True)
            self.is_mocked = True
            self.heater = None

    def get_state(self) -> Dict[str, Any]:
        """
        Gathers all relevant data from the heater library and formats it for the frontend.
        """
        if self.is_mocked or not self.heater:
            return { 'status': 'off', 'mode': 'temperature', 'setpoint': 20, 'powerLevel': 0, 
                    'ventilationLevel': 0, 'timer': None, 'errors': None, 
                    'readings': {'heaterTemp': 0, 'externalTemp': 0, 'voltage': 0, 'flameTemp': 0, 'panelTemp': 0}}
        
        # The library's getter methods return a tuple: (value, timestamp)
        # We only need the value (at index 0), with checks for None
        def get_val(getter, default=0):
            val = getter()
            return val[0] if val and val[0] is not None else default

        heater_status_code = get_val(self.heater.get_heater_status, default=(0,))[0]
        heater_mode_code = get_val(self.heater.get_heater_mode)

        mode_str = 'temperature' # Default
        if heater_mode_code == 4:
            mode_str = 'power'
        
        # The library's timer is a future timestamp. We need to calculate remaining minutes.
        run_timer_timestamp = self.heater.get_heater_timer()
        remaining_minutes = None
        if run_timer_timestamp and run_timer_timestamp > time.time():
            remaining_minutes = int((run_timer_timestamp - time.time()) / 60)
        
        return {
            'status': STATUS_MAP.get(heater_status_code, 'off'),
            'mode': mode_str,
            'setpoint': get_val(self.heater.get_heater_setpoint),
            'powerLevel': get_val(self.heater.get_heater_power_level),
            'ventilationLevel': 0, # Placeholder, as this is a separate command
            'timer': remaining_minutes,
            'errors': get_val(self.heater.get_heater_errors),
            'readings': {
                'heaterTemp': get_val(self.heater.get_heater_temperature),
                'externalTemp': get_val(self.heater.get_external_temperature),
                'voltage': get_val(self.heater.get_battery_voltage),
                'flameTemp': get_val(self.heater.get_flame_temperature),
                'panelTemp': get_val(self.heater.get_controller_temperature)
            }
        }

    # --- NEW METHOD TO FEED CABIN TEMPERATURE ---
    def update_cabin_temperature(self, temperature: int):
        """Feeds the cabin temperature to the heater library."""
        if not self.is_mocked and self.heater:
            self.heater.report_controller_temperature(int(temperature))

    # --- COMMANDS (Now simplified to pass-through) ---
    def shutdown(self):
        if not self.is_mocked:
            self.heater.shutdown()

    def turn_on_heating(self, mode: str, value: int, run_timer_minutes: Optional[int]):
        if self.is_mocked: return
        mode_code = MODE_MAP.get(mode, 2) # Default to temp mode
        
        setpoint = value if mode == 'temperature' else 0
        power = value if mode == 'power' else 0

        self.heater.turn_on_heater(mode=mode_code, setpoint=setpoint, power=power, timer=run_timer_minutes)

    def turn_on_ventilation(self, level: int, run_timer_minutes: Optional[int]):
        if not self.is_mocked:
            self.heater.turn_on_ventilation(power=level, timer=run_timer_minutes)

    def change_settings(self, mode: str, value: int):
        if self.is_mocked: return
        mode_code = MODE_MAP.get(mode, 2)
        
        setpoint = value if mode == 'temperature' else 0
        power = value if mode == 'power' else 0
        self.heater.change_settings(mode=mode_code, setpoint=setpoint, power=power)

    def cleanup(self):
        logging.info("Shutting down heater connection...")
        if not self.is_mocked and self.heater:
            self.shutdown()