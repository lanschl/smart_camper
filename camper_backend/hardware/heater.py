# hardware/heater.py
import time
import logging
# Import the new, robust heater controller
from .autotherm_heater_control.autoterm_heater import AutotermHeaterController
from typing import Dict, Any, Optional

# Map our frontend mode strings to the new library's internal mode strings
MODE_MAP = {
    'temperature': 'temp',
    'power': 'power',
    'ventilation': 'fan' 
}
# Map the library's internal mode strings back to frontend
MODE_MAP_REVERSE = {v: k for k, v in MODE_MAP.items()}


class HeaterController:
    """
    A controller that correctly wraps the NEW autoterm_heater library,
    translating its state for the frontend AND managing timers.
    """
    def __init__(self, serial_num: str, log_path: str):
        logging.info("Initializing Autoterm Heater Controller (V2)...")
        self.is_mocked = False
        self.heater: Optional[AutotermHeaterController] = None
        
        # --- NEW: Timer State Variables ---
        self.start_timer_timestamp: Optional[float] = None
        self.shutdown_timer_timestamp: Optional[float] = None
        self.pending_start_command: Optional[Dict[str, Any]] = None
        
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
            self.is_mocked = True
            self.heater = None

    # --- NEW: Main Timer Logic Method ---
    def check_timers(self):
        """
        Called periodically by the main app thread to check and execute timers.
        """
        if self.is_mocked: return

        current_time = time.time()
        
        # 1. Check for a pending shutdown
        if self.shutdown_timer_timestamp and current_time >= self.shutdown_timer_timestamp:
            logging.info("Heater runtime timer expired. Shutting down.")
            self.shutdown() # This will also clear the timers
            
        # 2. Check for a pending start
        if self.start_timer_timestamp and current_time >= self.start_timer_timestamp:
            logging.info(f"Heater start timer expired. Executing command: {self.pending_start_command}")
            if self.pending_start_command:
                command = self.pending_start_command.get('command')
                mode = self.pending_start_command.get('mode')
                value = self.pending_start_command.get('value')
                run_timer = self.pending_start_command.get('run_timer_minutes')
                
                if command == 'turn_on':
                    self.turn_on_heating(mode, value, run_timer)
                elif command == 'turn_on_ventilation':
                    self.turn_on_ventilation(value, run_timer)
            
            # Clear the start timer *after* executing
            self.start_timer_timestamp = None
            self.pending_start_command = None


    def get_state(self) -> Dict[str, Any]:
        """
        Gathers all relevant data from the heater library and formats it for the frontend.
        """
        if self.is_mocked or not self.heater:
            return { 'status': 'Error: Not Connected', 'mode': 'temperature', 'setpoint': 20, 'powerLevel': 0, 
                    'ventilationLevel': 0, 'timerStartIn': None, 'timerShutdownIn': None, 'errors': 'Not Connected', 
                    'readings': {'heaterTemp': 0, 'externalTemp': 0, 'voltage': 0, 'flameTemp': 0, 'panelTemp': 0}}
        
        status_data = self.heater.get_last_status()
        with self.heater.state_lock:
            lib_mode = self.heater.current_mode
            lib_setpoint = self.heater.current_setpoint

        frontend_mode = MODE_MAP_REVERSE.get(lib_mode, 'temperature')
        status_desc = status_data.get('description', 'Standby')
        error_desc = status_data.get('error', 'No Error')
        frontend_status = error_desc if error_desc != 'No Error' else status_desc
        
        setpoint_val = lib_setpoint if lib_mode == 'temp' else 0
        power_val = lib_setpoint if lib_mode == 'power' else 0
        vent_val = lib_setpoint if lib_mode == 'fan' else 0
        
        # --- NEW: Calculate remaining timer minutes ---
        remaining_start_min = None
        if self.start_timer_timestamp:
            remaining_start_min = max(0, int((self.start_timer_timestamp - time.time()) / 60))

        remaining_shutdown_min = None
        if self.shutdown_timer_timestamp:
            remaining_shutdown_min = max(0, int((self.shutdown_timer_timestamp - time.time()) / 60))

        return {
            'status': frontend_status,
            'mode': frontend_mode,
            'setpoint': setpoint_val,
            'powerLevel': power_val,
            'ventilationLevel': vent_val,
            'timerStartIn': remaining_start_min,     # Replaces old 'timer'
            'timerShutdownIn': remaining_shutdown_min, # New field for runtime
            'errors': error_desc,
            'readings': {
                'heaterTemp': status_data.get('heater_temp', 0),
                'externalTemp': status_data.get('external_temp'),
                'voltage': status_data.get('voltage', 0),
                'flameTemp': status_data.get('flame_temp', 0),
                'panelTemp': status_data.get('panel_temp', 0)
            }
        }

    def update_cabin_temperature(self, temperature: int):
        if not self.is_mocked and self.heater:
            self.heater.update_controller_temperature(int(temperature))

    # --- NEW: Timer Control Methods ---
    def set_start_timer(self, delay_minutes: int, action: Dict[str, Any]):
        """Sets a timer to start the heater later."""
        if delay_minutes > 0:
            self.start_timer_timestamp = time.time() + (delay_minutes * 60)
            self.pending_start_command = action
            logging.info(f"Heater start timer set for {delay_minutes} minutes. Action: {action}")
            # Ensure any existing run timer is cleared
            self.shutdown_timer_timestamp = None
        else:
            # If delay is 0, start now
            logging.info(f"Start timer delay is 0. Executing immediately: {action}")
            command = action.get('command')
            if command == 'turn_on':
                self.turn_on_heating(action.get('mode'), action.get('value'), action.get('run_timer_minutes'))
            elif command == 'turn_on_ventilation':
                self.turn_on_ventilation(action.get('value'), action.get('run_timer_minutes'))

    def cancel_start_timer(self):
        """Cancels a pending start timer."""
        logging.info("Heater start timer cancelled.")
        self.start_timer_timestamp = None
        self.pending_start_command = None

    # --- Updated Command Methods ---
    def shutdown(self):
        if not self.is_mocked and self.heater:
            self.heater.turn_off()
        # Always clear all timers on shutdown
        self.start_timer_timestamp = None
        self.pending_start_command = None
        self.shutdown_timer_timestamp = None
        logging.info("Heater shutdown requested. All timers cleared.")

    def turn_on_heating(self, mode: str, value: int, run_timer_minutes: Optional[int]):
        if self.is_mocked or not self.heater: return
        
        lib_mode = MODE_MAP.get(mode)
        success = False
        if lib_mode == 'temp':
            success = self.heater.turn_on_temp_mode(int(value))
        elif lib_mode == 'power':
            success = self.heater.turn_on_power_mode(int(value))
        
        if success:
            # Clear any pending start timer
            self.start_timer_timestamp = None
            self.pending_start_command = None
            # Set the new shutdown timer
            if run_timer_minutes and run_timer_minutes > 0:
                self.shutdown_timer_timestamp = time.time() + (run_timer_minutes * 60)
                logging.info(f"Heater started in {mode} mode. Shutdown timer set for {run_timer_minutes} minutes.")
            else:
                self.shutdown_timer_timestamp = None
                logging.info(f"Heater started in {mode} mode. No shutdown timer set.")


    def turn_on_ventilation(self, level: int, run_timer_minutes: Optional[int]):
        if self.is_mocked or not self.heater: return

        if self.heater.turn_on_fan_only(int(level)):
            # Clear any pending start timer
            self.start_timer_timestamp = None
            self.pending_start_command = None
            # Set the new shutdown timer
            if run_timer_minutes and run_timer_minutes > 0:
                self.shutdown_timer_timestamp = time.time() + (run_timer_minutes * 60)
                logging.info(f"Heater ventilation started. Shutdown timer set for {run_timer_minutes} minutes.")
            else:
                self.shutdown_timer_timestamp = None
                logging.info("Heater ventilation started. No shutdown timer set.")

    def change_settings(self, mode: str, value: int):
        """
        Changes the settings by re-sending the appropriate 'turn_on' command.
        This also RESETS the shutdown timer to whatever the new command's timer is.
        (Assuming the frontend sends run_timer_minutes with this command)
        """
        if self.is_mocked or not self.heater: return
        
        lib_mode = MODE_MAP.get(mode)
        logging.info(f"Changing heater settings to mode '{lib_mode}' with value '{value}'")

        # To change settings, we just re-call the main 'turn_on' methods.
        # The frontend needs to send the desired 'run_timer_minutes' (even if it's null)
        # as part of the 'change_setting' command payload.
        
        # We assume the frontend doesn't send a timer with 'change_setting',
        # so we preserve the *existing* shutdown timer.
        existing_shutdown_timer_minutes = None
        if self.shutdown_timer_timestamp:
             existing_shutdown_timer_minutes = max(0, int((self.shutdown_timer_timestamp - time.time()) / 60))

        if lib_mode == 'temp':
            self.turn_on_heating(mode, value, existing_shutdown_timer_minutes)
        elif lib_mode == 'power':
            self.turn_on_heating(mode, value, existing_shutdown_timer_minutes)
        elif lib_mode == 'fan':
            self.turn_on_ventilation(value, existing_shutdown_timer_minutes)

    def cleanup(self):
        logging.info("Shutting down heater connection...")
        if not self.is_mocked and self.heater:
            self.heater.cleanup()