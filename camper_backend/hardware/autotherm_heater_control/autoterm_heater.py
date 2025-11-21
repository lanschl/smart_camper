#!/usr/bin/python3
# Filename: autoterm_heater.py
#
# This file is the new, robust heater control library adapted from your
# working Windows script. It is designed to be imported and used as a class.
#
import logging
import serial
from logging.handlers import RotatingFileHandler
import serial.tools.list_ports
import time
import threading
import glob
import os
from typing import Dict, Any, Optional, Tuple

# --- Configuration ---
HEARTBEAT_INTERVAL_SECONDS = 4
RETRY_INTERVAL_SECONDS = 15

# --- Mappings (From new documentation) ---
status_text = {
    (0, 1): 'Standby', (1, 0): 'Starting - Cooling Sensor', (1, 1): 'Starting - Ventilation',
    (2, 0): 'Starting Preparation', (2, 1): 'Starting - Glow Plug', (2, 2): 'Starting - Ignition 1', (2, 3): 'Starting - Ignition 2',
    (2, 4): 'Starting - Heating Chamber', (3, 0): 'Heating', (3, 4): 'Cooling Down',
    (3, 5): 'Ventilating (Setpoint Reached)', (3, 35): 'Fan-Only Mode', (4, 0): 'Shutting Down'
}

error_text = {
    # --- Codes Updated According to PDF Page 1 (0-15) ---
    0: 'No Error',
    1: 'Overheating (Heat Exchanger)', 
    2: 'Possible Overheating (Intake Temp Sensor / Control Panel > 55°C)', 
    3: 'Under-voltage (Power Supply too low)', 
    4: 'Over-voltage (Power Supply too high)', 
    5: 'Faulty Temperature Sensor (Air 2D) or Flame Indicator',
    6: 'Faulty Internal Circuit Board Temperature Sensor (Non-replaceable)', 
    7: 'Overheating Sensor Not Measurable / Cable Defect',
    8: 'Fan Motor Failure (Incorrect speed/Stuck)',
    9: 'Faulty Glow Plug', 
    10: 'Fan Motor Not Reaching Necessary Speed', 
    11: 'Faulty Air Temperature Sensor (Air 8D)',
    12: 'Over-voltage Shutdown (>16V for 12V, >30V for 24V)', 
    13: 'Heater Start Failure (Two failed attempts)', 
    14: 'Overheating (Exhaust / Hot Air Outlet Temp Sensor)', 
    15: 'Battery Voltage Too Low (<10V for 12V, <20V for 24V)', 
    16: 'Temperature Sensor Did Not Cool Down (Ventilation/Purge Time Exceeded)',
    17: 'Faulty Fuel Pump (Short Circuit or Break in Wiring)',
    20: 'Heater Start Failure / Communication Error (Control Panel to Circuit Board - Green Wire)',
    27: 'Fan Motor Does Not Turn (Bearing/Rotor/Foreign Object Issue)',
    28: 'Fan Motor Turns, Speed Not Regulated (Defective Control/Main Board)',
    29: 'Ignition Flame Disturbance During Heater Operation (Flameout, Fuel/Air supply issue)',
    30: 'Heater Start Failure / Communication Error (Control Panel to Circuit Board - White Wire)',
    31: 'Overheating at Hot Air Outlet Temperature Sensor (Air 8D model)',
    32: 'Malfunction of Air Intake Temperature Sensor (Air 8D model)',
    33: 'Heater Control is Blocked (Occurs after 3 consecutive Overheating Errors)',
    34: 'Incorrect Component Mounting (Sensor installed in the wrong location)',
    35: 'Flame Malfunction (Due to Power Supply Voltage Drop)',
    36: 'Flame Indicator Temperature Above Normal',
    78: 'Flame Malfunction During Operation (Air bubbles in fuel line, pump error, or sensor fault)',
}

class AutotermHeaterController:
    """
    A robust controller for the Autoterm heater, based on the new,
    working communication protocol.
    """
    def __init__(self, serial_num: str, log_path: str, log_level: int = logging.INFO, baudrate: int = 9600):
        self.serial_num = serial_num
        self.port = None
        self.baudrate = baudrate
        self.comm_lock = threading.Lock()
        self.ser = None
        self.is_initialized = False
        self.connection_error_logged = False

        # --- Internal State ---
        self.state_lock = threading.Lock()
        self.last_status: Dict[str, Any] = {}
        self.current_mode = 'off' # 'off', 'temp', 'power', 'fan'
        self.current_setpoint = 0
        self.cabin_temperature = 20 # Default, will be updated by heater.py
        self.timer_end_time: Optional[float] = None # Timestamp when timer expires
        
        # --- Logging ---
        self.logger = logging.getLogger("AutotermHeater") 
        self.logger.setLevel(log_level)
        self.logger.propagate = False
        # Check if handler exists to avoid adding it twice on re-init
        if not self.logger.hasHandlers():
            try:
                # 1. Ensure directory exists
                log_dir = os.path.dirname(log_path)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)

                # 2. Use RotatingFileHandler (Max 5MB per file, keep 5 backups)
                handler = RotatingFileHandler(
                    log_path, 
                    maxBytes=5*1024*1024, # 5 MB
                    backupCount=5
                )
                
                formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
                handler.setFormatter(formatter)
                handler.setLevel(logging.DEBUG) 
                self.logger.addHandler(handler)
                
                self.logger.info(f"Heater logging initialized. Writing to: {log_path}")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to set up heater logger: {e}")

        # --- Worker Thread ---
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._connection_manager_worker, daemon=True)

    def start(self) -> bool:
        """Starts the background connection manager thread."""
        if not self.worker_thread.is_alive():
            self.logger.info("Starting Heater Connection Manager Thread...")
            self.worker_thread.start()
        return True

    def _find_serial_port(self):
        """Uses the serial number to find the correct /dev/tty* device file."""
        try:
            link_path_pattern = f"/dev/serial/by-id/*{self.serial_num}*"
            matching_links = glob.glob(link_path_pattern)
            if matching_links:
                self.port = os.path.realpath(matching_links[0])
                self.logger.info(f"Found serial adapter by ID '{self.serial_num}' at '{self.port}'")
                return True
            else:
                self.logger.warning(f"Serial device with ID '{self.serial_num}' NOT found.")
                
                # Diagnostic: List what IS there
                try:
                    available = glob.glob("/dev/serial/by-id/*")
                    if available:
                        self.logger.info(f"Available devices in /dev/serial/by-id/: {available}")
                    else:
                        self.logger.info("No devices found in /dev/serial/by-id/.")
                except Exception:
                    pass

                # Fallback for testing/other OS
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    if self.serial_num in (p.serial_number or ""):
                        self.port = p.device
                        self.logger.info(f"Found serial adapter by serial number at '{self.port}'")
                        return True
        except Exception as e:
            self.logger.error(f"Error while searching for serial device by ID: {e}")
        return False

    def connect(self) -> bool:
        if not self.port:
            self.logger.error("Cannot connect: Serial port not found.")
            return False
        try:
            self.ser = serial.Serial(
                self.port, self.baudrate, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1.0
            )
            self.logger.info(f"Successfully opened serial port {self.port}")
            return True
        except serial.SerialException as e:
            self.logger.error(f"Error opening serial port {self.port}: {e}")
            return False

    def initialize_session(self) -> bool:
        with self.comm_lock:
            if not self.ser: return False
            self.logger.info("Initializing communication session...")
            self.logger.debug("Sending wake-up sequence (12x 0x1B)...")
            for _ in range(12):
                self.ser.write(b'\x1b')
                time.sleep(0.05)
            self.ser.reset_input_buffer()
        
        self.logger.info("Checking connection with 'Get Version' command...")
        version_payload = self._send_command(0x06, log_prefix="Init")
        if version_payload and len(version_payload) == 5:
            version_str = ".".join(map(str, version_payload[0:4]))
            self.logger.info(f"Initialization successful! Heater version: {version_str}")
            self.is_initialized = True
            return True
        else:
            self.logger.error("Initialization failed. Heater did not respond correctly.")
            return False

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial port closed.")

    def cleanup(self):
        """Shuts down the worker thread and closes the serial connection."""
        self.logger.info("Cleaning up heater connection...")
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        
        if self.is_initialized:
            self.turn_off() # Send final shutdown command
            
        self.close()
        self.logger.info("Cleanup complete.")

    def _calculate_crc(self, data: bytes) -> bytes:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001: crc = (crc >> 1) ^ 0xA001
                else: crc >>= 1
        return crc.to_bytes(2, 'big')

    def _build_message(self, msg_type: int, payload: bytes = b'') -> bytes:
        header = bytearray([0xAA, 0x03, len(payload), 0x00, msg_type])
        return (header + payload) + self._calculate_crc(header + payload)

    def _send_command(self, msg_type: int, payload: bytes = b'', log_prefix: str = "CMD") -> Optional[bytes]:
        with self.comm_lock:
            if not self.ser or not self.ser.is_open:
                self.logger.error(f"[{log_prefix}] Serial port not open.")
                return None
            
            command = self._build_message(msg_type, payload)
            self.logger.info(f"[{log_prefix}] SEND: {command.hex(' ').upper()}")
            
            try:
                self.ser.reset_input_buffer()
                self.ser.write(command)
                time.sleep(0.3) # Wait for response
                raw_response = self.ser.read_all()
            except serial.SerialException as e:
                self.logger.error(f"Serial communication error: {e}")
                return None

            if not raw_response:
                self.logger.warning(f"[{log_prefix}] No response from heater.")
                return None

            start_index = raw_response.find(0xAA)
            if start_index == -1:
                self.logger.debug(f"No preamble (0xAA) in response: {raw_response.hex(' ')}")
                return None
            if start_index > 0:
                self.logger.debug(f"Trimmed {start_index} garbage bytes from response.")
            
            trimmed_response = raw_response[start_index:]
            if len(trimmed_response) < 7:
                self.logger.debug(f"Response too short: {trimmed_response.hex(' ')}")
                return None
            
            payload_length = trimmed_response[2]
            expected_len = 5 + payload_length + 2
            
            if len(trimmed_response) != expected_len:
                self.logger.warning(f"Response length mismatch. Got {len(trimmed_response)}, expected {expected_len}. Resp: {trimmed_response.hex(' ')}")
                return None
                
            response_data = trimmed_response[:-2]
            received_crc = trimmed_response[-2:]
            calculated_crc = self._calculate_crc(response_data)
            
            if calculated_crc != received_crc:
                self.logger.warning(f"[{log_prefix}] Checksum mismatch! Got {received_crc.hex()}, Exp {calculated_crc.hex()}")
                return None
            
            # Return just the payload
            return response_data[5:]
    
    def _connect_and_initialize(self) -> bool:
        """Attempts to find port, connect, and handshake."""
        if not self._find_serial_port():
            return False
        
        # Reuse your existing logic, but wrapped safely
        if self.connect() and self.initialize_session():
            self.logger.info(f"CONNECTED: Heater found on {self.port}")
            return True
        
        self.close()
        return False

    def _connection_manager_worker(self):
        """Main loop: Handles BOTH reconnection and heartbeat."""
        while not self.stop_event.is_set():
            
            # CASE 1: If not connected, try to connect
            if not self.is_initialized:
                if self._connect_and_initialize():
                    self.is_initialized = True
                    self.connection_error_logged = False
                else:
                    if not self.connection_error_logged:
                        self.logger.warning(f"Heater not found. Retrying every {RETRY_INTERVAL_SECONDS}s...")
                        self.connection_error_logged = True
                    time.sleep(RETRY_INTERVAL_SECONDS)
                    continue 

            # CASE 2: Connected? Run Heartbeat
            try:
                temp_to_report = 20
                mode = 'off'
                with self.state_lock:
                    mode = self.current_mode
                    temp_to_report = self.cabin_temperature
                
                if mode == 'temp':
                    self.report_controller_temperature(temp_to_report)

                status = self.get_status()
                
                if status:
                    with self.state_lock:
                        self.last_status = status
                        
                        # Check Timer
                        if self.timer_end_time and time.time() >= self.timer_end_time:
                            self.logger.info("Timer expired! Shutting down heater.")
                            # We need to call turn_off, but turn_off acquires state_lock.
                            # So we release it first? No, turn_off acquires it.
                            # But we are currently holding it? Yes, we are inside `with self.state_lock`.
                            # Wait, `self.last_status = status` is inside the lock.
                            # We should check timer OUTSIDE the lock or handle it carefully.
                            pass 

                    # Check timer outside the lock to avoid deadlock if turn_off uses the lock
                    if self.timer_end_time and time.time() >= self.timer_end_time:
                         self.turn_off()

                else:
                    # If status fails, we lost connection
                    self.logger.warning("Lost connection to heater. Resetting...")
                    self.is_initialized = False
                    self.close()
            
            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}")
                self.is_initialized = False
                self.close()

            self.stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)
    
    def get_last_status(self) -> Dict[str, Any]:
        """Returns the last known status from the worker thread."""
        with self.state_lock:
            status = self.last_status.copy()
            if self.timer_end_time:
                remaining = int((self.timer_end_time - time.time()) / 60)
                if remaining < 0: remaining = 0
                status['remaining_minutes'] = remaining
            else:
                status['remaining_minutes'] = None
            return status

    def update_controller_temperature(self, temp: int):
        """Receives the real cabin temperature from the main app."""
        with self.state_lock:
            self.cabin_temperature = int(temp)
        self.logger.debug(f"Cabin temperature updated to: {temp}°C")

    # --- Public Commands ---

    def turn_on_power_mode(self, level: int, timer_minutes: Optional[int] = None) -> bool:
        if not self.is_initialized: 
            return False
        self.logger.info(f"Sending command: POWER mode at level {level}...")
        payload = bytes([0x01, 0x00, 0x04, 0x10, 0x00, level])
        success = self._send_command(0x01, payload=payload) is not None
        if success:
            with self.state_lock:
                self.current_mode = 'power'
                self.current_setpoint = level
                if timer_minutes:
                    self.timer_end_time = time.time() + (timer_minutes * 60)
                    self.logger.info(f"Timer set for {timer_minutes} minutes.")
                else:
                    self.timer_end_time = None
        return success

    def turn_on_temp_mode(self, setpoint: int, timer_minutes: Optional[int] = None) -> bool:
        if not self.is_initialized: 
            return False
        self.logger.info(f"Sending command: TEMPERATURE mode with setpoint {setpoint}°C...")
        payload = bytes([0x01, 0x00, 0x02, setpoint, 0x00, 0x08])
        success = self._send_command(0x01, payload=payload) is not None
        if success:
            with self.state_lock:
                self.current_mode = 'temp'
                self.current_setpoint = setpoint
                if timer_minutes:
                    self.timer_end_time = time.time() + (timer_minutes * 60)
                    self.logger.info(f"Timer set for {timer_minutes} minutes.")
                else:
                    self.timer_end_time = None
        return success

    def turn_on_fan_only(self, level: int, timer_minutes: Optional[int] = None) -> bool:
        if not self.is_initialized: 
            return False
        self.logger.info(f"Sending command: FAN ONLY mode at level {level}...")
        payload = bytes([0xFF, 0xFF, level, 0xFF])
        success = self._send_command(0x23, payload=payload) is not None
        if success:
            with self.state_lock:
                self.current_mode = 'fan'
                self.current_setpoint = level
                if timer_minutes:
                    self.timer_end_time = time.time() + (timer_minutes * 60)
                    self.logger.info(f"Timer set for {timer_minutes} minutes.")
                else:
                    self.timer_end_time = None
        return success
    
    def turn_off(self) -> bool:
        if not self.is_initialized: 
            return False
        self.logger.info("Sending SHUTDOWN command...")
        success = self._send_command(0x03) is not None
        if success:
            with self.state_lock:
                self.current_mode = 'off'
                self.current_setpoint = 0
                self.timer_end_time = None
        return success

    def report_controller_temperature(self, temp: int) -> bool:
        self.logger.info(f"Reporting controller temp: {temp}°C")
        # Temperature is a signed byte
        payload = int(temp).to_bytes(1, 'big', signed=True)
        return self._send_command(0x11, payload=payload) is not None

    def get_status(self) -> Optional[Dict[str, Any]]:
        payload = self._send_command(0x0F, log_prefix="Heartbeat")
        if not payload or len(payload) < 19:
            self.logger.warning(f"GET_STATUS: Invalid payload received. {payload.hex(' ') if payload else 'No payload'}")
            return None
    
        def parse_signed(b):
            if b <-20:
                return b + 256
            return b
        
        try:
            status_code = (payload[0], payload[1])
            status_desc = status_text.get(status_code, f"Unknown {status_code}")
            error_code = payload[2]
            error_desc = error_text.get(error_code, f"Unknown Error {error_code}")


            heater_temp = parse_signed(payload[3]) # Heater Temp
            # external_temp = parse_signed(payload[4]) if payload[4] != 0x7F else None # External sensor
            voltage = payload[6] / 10.0
            flame_temp = parse_signed(payload[8])   
            
            fan_rpm_set = payload[11] * 60
            fan_rpm_actual = payload[12] * 60
            fuel_pump_freq = payload[14] / 100.0

            log_summary = (
                f"Parsed Status -> Mode: {status_desc} [{status_code[0]}.{status_code[1]}] | "
                f"Error: {error_desc} | Voltage: {voltage:.1f}V | "
                f"Temps (Heater/Flame): {heater_temp}°C/{flame_temp}°C | "
                f"Fan (Set/Actual): {fan_rpm_set}/{fan_rpm_actual} RPM | Pump: {fuel_pump_freq:.2f}Hz"
            )
            self.logger.info(log_summary)

            return {
                "status_tuple": status_code,
                "description": status_desc,
                "error_code": error_code,
                "error": error_desc,
                "voltage": voltage,
                "heater_temp": heater_temp,
                "flame_temp": flame_temp,
                "fan_rpm": fan_rpm_actual,
                "fuel_pump_freq": fuel_pump_freq
            }
        except Exception as e:
            self.logger.error(f"Failed to parse status payload: {payload.hex(' ')} - Error: {e}", exc_info=True)
            return None
        
    