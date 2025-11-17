# hardware/heater.py
import time
import logging
# Import the new, robust heater controller
from .autotherm_heater_control.autoterm_heater import AutotermHeaterController
from typing import Dict, Any, Optional

# --- Status Translation ---
# This map translates the new library's detailed status descriptions
# into the simple status strings your frontend expects.
#
# New Library Statuses:
# 'Standby', 'Starting - Cooling Sensor', 'Starting - Ventilation',
# 'Starting - Glow Plug', 'Starting - Ignition 1', 'Starting - Ignition 2',
# 'Starting - Heating Chamber', 'Heating', 'Cooling Down',
# 'Ventilating (Setpoint Reached)', 'Fan-Only Mode', 'Shutting Down'
#
# Frontend Statuses:
# 'off', 'starting', 'warming_up', 'running', 'shutting_down'

def translate_status(status_desc: str) -> str:
    """Translates detailed status text to simple frontend status."""
    if 'Starting' in status_desc:
        return 'starting'
    if 'Shutting Down' in status_desc or 'Cooling Down' in status_desc:
        return 'shutting_down'
    if 'Heating' in status_desc or 'Fan-Only Mode' in status_desc or 'Ventilating' in status_desc:
        return 'running'
    # Default to 'off' for 'Standby' or unknown
    return 'off'

# Map our frontend mode strings to the new library's internal mode strings
MODE_MAP = {
    'temperature': 'temp',
    'power': 'power',
    'ventilation': 'fan' # Added for fan-only mode
}
# Map the library's internal mode strings back to frontend
MODE_MAP_REVERSE = {v: k for k, v in MODE_MAP.items()}


class HeaterController:
    """
    A controller that correctly wraps the NEW autoterm_heater library,
    translating its state for the frontend.
    """
    def __init__(self, serial_num: str, log_path: str):

        self.logger = logging.getLogger("AutotermHeater")

        logging.info("Initializing Autoterm Heater Controller (V2)...")
        self.is_mocked = False
        self.heater: Optional[AutotermHeaterController] = None
        try:
            self.heater = AutotermHeaterController(
                serial_num=serial_num,
                log_path=log_path,
                log_level=logging.INFO
            )
            if not self.heater.start():
                raise RuntimeError("Failed to connect to or initialize heater.")
            
            logging.info("Heater V2 connection successfully initialized and worker started.")
        except Exception as e:
            logging.error(f"Failed to initialize heater V2 controller: {e}", exc_info=True)
            self.logger.error(f"Failed to initialize heater V2 controller: {e}")
            self.is_mocked = True
            self.heater = None

    def get_state(self) -> Dict[str, Any]:
        """
        Gathers all relevant data from the heater library and formats it for the frontend.
        """
        if self.is_mocked or not self.heater:
            # Return a default mocked state if initialization failed
            return { 'status': 'off', 'mode': 'temperature', 'setpoint': 20, 'powerLevel': 0, 
                    'ventilationLevel': 0, 'timer': None, 'errors': 'No Error', 
                    'readings': {'heaterTemp': 0, 'externalTemp': 0, 'voltage': 0, 'flameTemp': 0, 'panelTemp': 0}}
        
        # Get the latest status packet from the heater's worker thread
        status_data = self.heater.get_last_status()
        
        # Get the heater's internal mode and setpoint
        with self.heater.state_lock:
            lib_mode = self.heater.current_mode
            lib_setpoint = self.heater.current_setpoint

        frontend_mode = MODE_MAP_REVERSE.get(lib_mode, 'temperature')
        status_desc = status_data.get('description', 'Standby')
        frontend_status = translate_status(status_desc)
        
        # The new library doesn't support timers, so 'timer' is always None.
        
        # Separate setpoint/power/ventilation based on the current mode
        setpoint_val = lib_setpoint if lib_mode == 'temp' else 0
        power_val = lib_setpoint if lib_mode == 'power' else 0
        vent_val = lib_setpoint if lib_mode == 'fan' else 0
        
        return {
            'status': frontend_status,
            'mode': frontend_mode,
            'setpoint': setpoint_val,
            'powerLevel': power_val,
            'ventilationLevel': vent_val,
            'timer': None, # Timers are not supported by the new library
            'errors': status_data.get('error', 'No Error'),
            'readings': {
                'heaterTemp': status_data.get('heater_temp', 0),
                'externalTemp': status_data.get('external_temp'),
                'voltage': status_data.get('voltage', 0),
                'flameTemp': status_data.get('flame_temp', 0),
                'panelTemp': status_data.get('panel_temp', 0)
            }
        }

    # --- NEW METHOD TO FEED CABIN TEMPERATURE ---
    def update_cabin_temperature(self, temperature: int):
        """Feeds the real cabin temperature to the heater library."""
        if not self.is_mocked and self.heater:
            # This calls the new library's method
            self.heater.update_controller_temperature(int(temperature))

    # --- COMMANDS (Now simplified to pass-through) ---
    def shutdown(self):
        if not self.is_mocked and self.heater:
            self.heater.turn_off()

    def turn_on_heating(self, mode: str, value: int, run_timer_minutes: Optional[int]):
        """
        Starts heating or power mode.
        NOTE: run_timer_minutes is not supported by the new library and will be ignored.
        """
        if self.is_mocked or not self.heater: return
        
        lib_mode = MODE_MAP.get(mode)
        
        if lib_mode == 'temp':
            self.heater.turn_on_temp_mode(int(value))
        elif lib_mode == 'power':
            self.heater.turn_on_power_mode(int(value))
        
        if run_timer_minutes:
            self.logger.warning("run_timer_minutes is not supported by the new heater library and was ignored.")

    def turn_on_ventilation(self, level: int, run_timer_minutes: Optional[int]):
        """
        Starts fan-only mode.
        NOTE: run_timer_minutes is not supported by the new library and will be ignored.
        """
        if not self.is_mocked and self.heater:
            self.heater.turn_on_fan_only(int(level))
        
        if run_timer_minutes:
            self.logger.warning("run_timer_minutes is not supported by the new heater library and was ignored.")

    def change_settings(self, mode: str, value: int):
        """
        Changes the settings by re-sending the appropriate 'turn_on' command.
        """
        if self.is_mocked or not self.heater: return
        
        lib_mode = MODE_MAP.get(mode)

        if lib_mode == 'temp':
            self.heater.turn_on_temp_mode(int(value))
        elif lib_mode == 'power':
            self.heater.turn_on_power_mode(int(value))
        elif lib_mode == 'fan':
            # This wasn't a case before, but good to handle
            self.heater.turn_on_fan_only(int(value))

    def cleanup(self):
        self.logger.info("Shutting down heater connection...")
        if not self.is_mocked and self.heater:
            self.heater.cleanup()