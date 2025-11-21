import subprocess
import re
import sys
import logging
import threading
import time
from typing import Optional, Dict

class BMSReader:
    """
    Reads JKBMS data by calling the 'jkbms' command-line tool from mppsolar.
    Now uses a background thread to prevent blocking the main application loop.
    """
    def __init__(self, mac_address: str, protocol: str):
        self.mac = mac_address
        self.protocol = protocol
        self.command = "getCellData"
        self.jkbms_path = self._find_jkbms_path()
        self.is_mocked = not bool(self.jkbms_path)
        
        self.last_data = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        
        # Start the background worker
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _find_jkbms_path(self) -> Optional[str]:
        """Finds the full path to the jkbms executable."""
        try:
            path_process = subprocess.run(["which", "jkbms"], capture_output=True, text=True, check=True, encoding='utf-8')
            path = path_process.stdout.strip()
            if path:
                logging.info(f"Found jkbms executable at: {path}")
                return path
        except (FileNotFoundError, subprocess.CalledProcessError):
            logging.error("Could not find 'jkbms' executable in system PATH.")
            logging.error("Please ensure mppsolar is installed and venv is active.")
        return None

    def _worker(self):
        """Background worker to poll BMS data."""
        while not self.stop_event.is_set():
            try:
                data = self._fetch_data()
                with self.lock:
                    self.last_data = data
            except Exception as e:
                logging.error(f"Error in BMS worker: {e}")
            
            # Wait for 15 seconds before next poll
            # We use wait() on the event so we can exit immediately if stopped
            if self.stop_event.wait(15):
                break

    def _fetch_data(self) -> Optional[Dict[str, float]]:
        """Internal method to actually call the jkbms command."""
        if self.is_mocked:
            return {'batterySoC': 85.5, 'batteryVoltage': 13.1, 'batteryAmperage': 2.3, 'batteryPower': 30.1}

        cmd = [self.jkbms_path, "-p", self.mac, "-P", self.protocol, "-c", self.command]
        logging.info(f"Running BMS command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True, encoding='utf-8')
            
            parsed_data = {}
            # Regex to find lines with: "parameter_name   value   unit"
            data_regex = re.compile(r"^\s*([\w_]+)\s+([\d.-]+)\s*(\S*)\s*$")

            for line in result.stdout.splitlines():
                match = data_regex.match(line)
                if match:
                    parsed_data[match.group(1).lower()] = float(match.group(2))
            
            if not parsed_data:
                logging.warning("BMS command ran but no data was parsed.")
                return None
            
            # Map the parsed keys to the keys our frontend expects
            final_data = {
                'batterySoC': parsed_data.get("percent_remain", 0.0),
                'batteryVoltage': parsed_data.get("battery_voltage", 0.0),
                'batteryAmperage': parsed_data.get("battery_current", 0.0),
                'batteryPower': parsed_data.get("battery_power", 0.0)
            }
            logging.info(f"Successfully read and parsed from BMS: {final_data}")
            return final_data

        except subprocess.CalledProcessError as e:
            # This usually happens if the BMS is out of range or busy
            logging.warning(f"BMS command failed (Device likely offline/busy). STDERR: {e.stderr.strip()}")
            return None
        except subprocess.TimeoutExpired:
            logging.warning("BMS connection timed out. Is it on and in range?")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while reading BMS: {e}")
            return None

    def read_data(self) -> Optional[Dict[str, float]]:
        """Returns the latest cached data immediately."""
        with self.lock:
            return self.last_data

    def stop(self):
        """Stops the background worker."""
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=1)

    def cleanup(self):
        """Alias for stop, used by app.py cleanup."""
        self.stop()