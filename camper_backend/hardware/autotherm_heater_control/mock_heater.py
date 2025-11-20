# hardware/mock_heater.py
import logging
import threading
import time
import re
from typing import Dict, Any

# This class will simulate the AutotermHeaterController
class MockAutotermHeaterController:
    """
    A mock controller that replays status updates from a log file.
    It mimics the interface of the real AutotermHeaterController.
    """
    def __init__(self, serial_num: str, log_path: str, **kwargs):
        self.logger = logging.getLogger("MockAutotermHeater")
        self.logger.info("--- INITIALIZING MOCK HEATER CONTROLLER ---")
        
        # State variables to match the real controller
        self.state_lock = threading.Lock()
        self.last_status: Dict[str, Any] = {}
        self.is_initialized = False
        self.current_mode = 'off'
        self.current_setpoint = 0
        self.cabin_temperature = 20
        self.timer_end_time = None

        # Data for the simulation
        self._status_log_entries = []
        self._log_index = 0
        self._parse_log_file()

        # Worker thread for replaying data
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._mock_worker, daemon=True)

    def _parse_log_file(self):
        """Reads the heater.mock.log file and parses all status lines."""
        self.logger.info("Parsing mock log file...")
        try:
            with open('/home/lukas/smart_camper/camper_backend/heater.mock.log', 'r') as f:
                for line in f:
                    if "Parsed Status ->" in line:
                        entry = self._parse_line(line)
                        if entry:
                            self._status_log_entries.append(entry)
            self.logger.info(f"Successfully parsed {len(self._status_log_entries)} status entries from log.")
        except FileNotFoundError:
            self.logger.error("heater.mock.log not found! Mock will not have data.")
        except Exception as e:
            self.logger.error(f"Error parsing log file: {e}")

    def _parse_line(self, line: str) -> Dict[str, Any] | None:
        """Uses regex to extract data from a single log line."""
        # This regex is built to match the format of your log file
        pattern = re.compile(
            r"Mode: (.*?) \[(.*?)\]\s*\|\s*Error: (.*?)\s*\|\s*Voltage: ([\d.]+)V\s*\|\s*Temps \(Heater/Flame/External\): (-?\d+)°C/(-?\d+)°C/(.*?)°C"
        )
        match = pattern.search(line)
        if not match:
            return None
            
        def parse_signed(val_str):
            val = int(val_str)
            # Fix for negative values in log that represent high temps
            # If value is < -50 (unlikely to be real ambient), treat as unsigned wrap-around
            if val < -20:
                return val + 256
            return val
        
        ext_temp_str = match.group(7)
        # Store raw strings for debugging in the worker loop
        raw_heater_temp = match.group(5)
        raw_flame_temp = match.group(6)
        
        return {
            "description": match.group(1).strip(),
            "error": match.group(3).strip(),
            "voltage": float(match.group(4)),
            "heater_temp": parse_signed(raw_heater_temp),
            "flame_temp": parse_signed(raw_flame_temp), 
            "external_temp": int(ext_temp_str) if ext_temp_str != 'None' else None,
            "raw_heater_temp": raw_heater_temp,
            "raw_flame_temp": raw_flame_temp
        }

    def _mock_worker(self):
        """The worker loop that replays log data."""
        if not self._status_log_entries:
            self.logger.warning("No log entries to replay. Worker stopping.")
            return

        while not self.stop_event.is_set():
            # Get the next status from our parsed list
            next_status = self._status_log_entries[self._log_index]
            
            with self.state_lock:
                self.last_status = next_status
            
            # Log the status update AND the debug info the user requested
            self.logger.info(f"MOCK UPDATE: Status set to '{next_status.get('description')}'")
            
            # Re-calculate for display purposes to match user's request
            def parse_signed_debug(val_str):
                val = int(val_str)
                # Same fix here for debug output
                if val < -20:
                    return val + 256
                return val

            raw_ht = next_status.get('raw_heater_temp', '0')
            self.logger.info(f"heater_temp = {raw_ht}, after the applied parsed signed: {parse_signed_debug(raw_ht)}")

            # Move to the next entry, looping back to the start if we reach the end
            self._log_index = (self._log_index + 1) % len(self._status_log_entries)
            
            # Check Timer
            if self.timer_end_time and time.time() >= self.timer_end_time:
                self.logger.info("MOCK: Timer expired! Shutting down heater.")
                self.turn_off()

            # Wait for 2 seconds before the next update
            self.stop_event.wait(2)

    # --- Public methods that mimic the real controller ---
    def start(self) -> bool:
        self.logger.info("Starting Mock Heater worker thread...")
        self.is_initialized = True
        self.worker_thread.start()
        return True

    def get_last_status(self) -> Dict[str, Any]:
        with self.state_lock:
            status = self.last_status.copy()
            if self.timer_end_time:
                remaining = int((self.timer_end_time - time.time()) / 60)
                if remaining < 0: remaining = 0
                status['remaining_minutes'] = remaining
            else:
                status['remaining_minutes'] = None
            return status
            
    def cleanup(self):
        self.logger.info("Cleaning up mock heater...")
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1)

    # Mocked command methods just log that they were called
    def turn_on_power_mode(self, level: int, timer_minutes: int = None): 
        self.logger.info(f"MOCK COMMAND: turn_on_power_mode(level={level}, timer={timer_minutes})")
        if timer_minutes:
            self.timer_end_time = time.time() + (timer_minutes * 60)
        else:
            self.timer_end_time = None

    def turn_on_temp_mode(self, setpoint: int, timer_minutes: int = None): 
        self.logger.info(f"MOCK COMMAND: turn_on_temp_mode(setpoint={setpoint}, timer={timer_minutes})")
        if timer_minutes:
            self.timer_end_time = time.time() + (timer_minutes * 60)
        else:
            self.timer_end_time = None

    def turn_on_fan_only(self, level: int, timer_minutes: int = None): 
        self.logger.info(f"MOCK COMMAND: turn_on_fan_only(level={level}, timer={timer_minutes})")
        if timer_minutes:
            self.timer_end_time = time.time() + (timer_minutes * 60)
        else:
            self.timer_end_time = None

    def turn_off(self): 
        self.logger.info("MOCK COMMAND: turn_off()")
        self.timer_end_time = None
    def update_controller_temperature(self, temp: int): pass # No need to log this one