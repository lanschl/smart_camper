import logging
from .autotherm_heater_control.autoterm_heater import AutotermPassthrough, status_text
from typing import Dict, Any

# Map the library's integer status codes to the strings our frontend uses
STATUS_MAP = {
    0: 'off',
    1: 'starting',
    2: 'warming_up',
    3: 'running',
    4: 'shutting_down'
}

class HeaterController:
    """
    A controller class that wraps the autoterm_heater library to provide a clean
    interface for our main application.
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
            logging.error(f"Failed to initialize heater controller: {e}")
            self.is_mocked = True
            self.heater = None

    def get_state(self) -> Dict[str, Any]:
        """
        Gathers all relevant data from the heater and formats it for the frontend.
        """
        if self.is_mocked or not self.heater:
            # Return a default "off" state if there's an issue
            return {
                'status': 'off', 'mode': 'temperature', 'setpoint': 20, 'powerLevel': 0,
                'ventilationLevel': 0, 'timer': None, 'errors': None,
                'readings': {'heaterTemp': 0, 'externalTemp': 0, 'voltage': 0, 'flameTemp': 0, 'panelTemp': 0}
            }
        
        # The library stores values as tuples: (value, timestamp)
        # We just need the value (at index 0)
        heater_status_code = self.heater.get_heater_status()[0][0]
        heater_mode_code = self.heater.get_heater_mode()[0]

        # Determine mode string
        mode_str = 'temperature' # Default
        if heater_mode_code == 4:
            mode_str = 'power'
        # The library doesn't seem to differentiate ventilation mode here,
        # we control that via a separate command.

        return {
            'status': STATUS_MAP.get(heater_status_code, 'off'),
            'mode': mode_str,
            'setpoint': self.heater.get_heater_setpoint()[0],
            'powerLevel': self.heater.get_heater_power_level()[0],
            'ventilationLevel': 0, # Placeholder, controlled directly
            'timer': self.heater.get_heater_timer(), # This might need adjustment
            'errors': self.heater.get_heater_errors()[0],
            'readings': {
                'heaterTemp': self.heater.get_heater_temperature()[0],
                'externalTemp': self.heater.get_external_temperature()[0],
                'voltage': self.heater.get_battery_voltage()[0],
                'flameTemp': self.heater.get_flame_temperature()[0],
                'panelTemp': self.heater.get_controller_temperature()[0]
            }
        }

    # --- COMMANDS ---
    def shutdown(self):
        if not self.is_mocked:
            self.heater.shutdown()

    def turn_on_heating(self, mode: str, value: int):
        if self.is_mocked: return
        
        if mode == 'power':
            # mode=4 is power mode, value is power level
            self.heater.turn_on_heater(mode=4, power=value)
        else: # Default to temperature mode
            # mode=2 is controller temp, value is setpoint
            self.heater.turn_on_heater(mode=2, setpoint=value)

    def turn_on_ventilation(self, level: int):
        if not self.is_mocked:
            self.heater.turn_on_ventilation(level)

    def change_settings(self, mode: str, value: int):
        if self.is_mocked: return

        if mode == 'power':
            self.heater.change_settings(mode=4, power=value)
        else: # Temperature mode
            self.heater.change_settings(mode=2, setpoint=value)

    def cleanup(self):
        logging.info("Shutting down heater connection...")
        if not self.is_mocked:
            self.shutdown() # Ensure heater is told to shut down
            # The library's background thread is a daemon, so it will exit with the main app