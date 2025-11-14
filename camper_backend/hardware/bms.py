import subprocess
import re
import sys
import logging
from typing import Optional, Dict

class BMSReader:
    """
    Reads JKBMS data by calling the 'jkbms' command-line tool from mppsolar.
    """
    def __init__(self, mac_address: str, protocol: str):
        self.mac = mac_address
        self.protocol = protocol
        self.command = "getCellData"
        self.jkbms_path = self._find_jkbms_path()
        self.is_mocked = not bool(self.jkbms_path)

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

    def read_data(self) -> Optional[Dict[str, float]]:
        """Calls the jkbms command and parses the output."""
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
            logging.error(f"BMS command failed. STDERR: {e.stderr.strip()}")
            return None
        except subprocess.TimeoutExpired:
            logging.error("BMS connection timed out. Is it on and in range?")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while reading BMS: {e}")
            return None