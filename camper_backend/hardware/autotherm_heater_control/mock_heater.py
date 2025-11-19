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
            return val if val <= 127 else val - 256
        
        ext_temp_str = match.group(7)
        return {
            "description": match.group(1).strip(),
            "error": match.group(3).strip(),
            "voltage": float(match.group(4)),
            "heater_temp": parse_signed(match.group(5)),
            "flame_temp": parse_signed(match.group(6)), 
            "external_temp": int(ext_temp_str) if ext_temp_str != 'None' else None,
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
            
            self.logger.info(f"MOCK UPDATE: Status set to '{next_status.get('description')}'")

            # Move to the next entry, looping back to the start if we reach the end
            self._log_index = (self._log_index + 1) % len(self._status_log_entries)
            
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
            return self.last_status.copy()
            
    def cleanup(self):
        self.logger.info("Cleaning up mock heater...")
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1)

    # Mocked command methods just log that they were called
    def turn_on_power_mode(self, level: int): self.logger.info(f"MOCK COMMAND: turn_on_power_mode(level={level})")
    def turn_on_temp_mode(self, setpoint: int): self.logger.info(f"MOCK COMMAND: turn_on_temp_mode(setpoint={setpoint})")
    def turn_on_fan_only(self, level: int): self.logger.info(f"MOCK COMMAND: turn_on_fan_only(level={level})")
    def turn_off(self): self.logger.info("MOCK COMMAND: turn_off()")
    def update_controller_temperature(self, temp: int): pass # No need to log this one