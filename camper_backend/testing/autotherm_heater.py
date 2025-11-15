#!/usr/bin/python3
# Filename: autoterm_heater.py

import logging
import serial
import serial.tools.list_ports as list_ports
import threading
import time

################
versionMajor = 0
versionMinor = 1
versionPatch = 3 # Increment patch version
################

# Updated status_text based on your provided documentation
status_text = {
    (0, 1): 'Standby',
    (1, 0): 'Cooling flame sensor',
    (1, 1): 'Ventilation',
    (2, 1): 'Heating glow plug',
    (2, 2): 'Ignition 1',
    (2, 3): 'Ignition 2',
    (2, 4): 'Heating combustion chamber',
    (3, 0): 'Heating',
    (3, 35): 'Only fan',
    (3, 4): 'Cooling down',
    (4, 0): 'Shutting down'
}

temp_source_text = {
    1: 'Internal sensor',
    2: 'Panel sensor (set temp message)',
    3: 'External sensor',
    4: 'No automatic temperature control'
}


class Message:
    def __init__(self, preamble, device, length, msg_id1, msg_id2, payload = b''):
        self.preamble = preamble
        self.device = device
        self.length = length
        self.msg_id1 = msg_id1
        self.msg_id2 = msg_id2
        self.payload = payload

class AutotermUtils:
    def crc16(self, package : bytes):
        crc = 0xffff
        for byte in package:
            crc ^= byte
            for i in range(8):
                if (crc & 0x0001) != 0:
                    crc >>= 1
                    crc ^= 0xa001
                else:
                    crc >>= 1;
        return crc.to_bytes(2, byteorder='big')

    def parse(self, package : bytes, minPacketSize = 7):
        # Allow initial non-AA bytes to be discarded
        idx = 0
        while idx < len(package) and package[idx] != 0xaa:
            idx += 1
        package = package[idx:]

        if len(package) < minPacketSize:
            # self.logger.debug(f'Parse: invalid length of package ({len(package)} < {minPacketSize})! ({package.hex()})')
            return 0
        if package[0] != 0xaa:
            # self.logger.debug(f'Parse: invalid bit 0 of package! ({package.hex()})')
            return 0
        
        expected_len = package[2] + minPacketSize
        if len(package) < expected_len: # Not enough bytes to even check CRC
            # self.logger.debug(f'Parse: not enough bytes for full package ({len(package)} < {expected_len})! ({package.hex()})')
            return 0

        if package[-2:] != self.crc16(package[:-2]):
            # self.logger.debug(f'Parse: invalid crc of package! ({package.hex()}) Expected: {self.crc16(package[:-2]).hex()} Got: {package[-2:].hex()}')
            return 0

        return Message(package[0], package[1], package[2], package[3], package[4], package[5:-2])

    def build(self, device, msg_id2, msg_id1=0x00, payload = b''):
        # We always want to be the "controller" sending messages (0x03)
        # Or in diagnostic mode, if it's a specific diagnostic message.
        # For this direct control, we'll assume we're acting as the controller (0x03) for most commands.
        # The heater responds with 0x04.
        # Diagnostic messages (0x02) can be sent by PC (0x00) or heater (0x01).
        
        # In a typical controller-to-heater scenario, the controller sends with device=0x03
        # and the heater responds with device=0x04.
        
        package = b'\xaa'+device.to_bytes(1, byteorder='big')+len(payload).to_bytes(1, byteorder='big')+msg_id1.to_bytes(1, byteorder='big')+msg_id2.to_bytes(1, byteorder='big')+payload

        return package + self.crc16(package)


class AutotermHeaterController(AutotermUtils):
    def __init__(self, serial_port=None, baudrate=9600, serial_num=None, log_level=logging.DEBUG):
        self.port = serial_port
        self.baudrate = baudrate
        self.serial_num = serial_num

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        handler = logging.StreamHandler() # Output to console for debugging
        formatter = logging.Formatter(fmt = '%(asctime)s  %(name)s %(levelname)s: %(message)s', datefmt='%d.%m.%Y %H:%M:%S')
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        self.logger.addHandler(handler)

        self.logger.info(f'AutotermHeaterController v {versionMajor}.{versionMinor}.{versionPatch} is starting.')

        self.__connected = False
        self.__ser = None # Single serial port for direct control

        self.__write_lock = threading.Lock()
        self.__connect()

        self.__working = False
        self.__start_working()

        # State storage (for debugging, we'll fetch these directly)
        self.__heater_state = {}
        self.__diagnostic_data = {}
        self.__heater_settings = {} # Added for settings
        
        # self.__write_lock = threading.Lock() # Use a lock for sending messages

    def __write_message(self, message):
        with self.__write_lock:
            try:
                if self.__ser and self.__ser.is_open:
                    bytes_written = self.__ser.write(message)
                    if bytes_written != len(message):
                        self.logger.critical(f'Cannot send whole message to serial port {self.__ser.port}!')
                    self.logger.debug(f'Sent: {message.hex()}')
                    return True
                else:
                    self.logger.error('Serial port not open for writing.')
                    return False
            except serial.serialutil.SerialException as e:
                self.logger.error(f'Serial write error to {self.port}: {e}')
                self.__connected = False
                return False
            except OSError as e:
                self.logger.error(f'OS error during serial write to {self.port}: {e}')
                self.__connected = False
                return False

    def __read_response(self, timeout=1.0):
        start_time = time.time()
        response_buffer = b''
        while time.time() - start_time < timeout:
            if self.__ser and self.__ser.in_waiting > 0:
                byte = self.__ser.read(1)
                if byte == b'\xaa': # Preamble found
                    response_buffer = byte
                    # Try to read the rest of the header and payload length
                    remaining_header = self.__ser.read(2)
                    if len(remaining_header) < 2:
                        continue # Not enough data, maybe a partial read
                    response_buffer += remaining_header
                    
                    payload_len = remaining_header[1]
                    # We need 4 more bytes (msg_id1, msg_id2, CRC1, CRC2) + payload
                    full_message_len = 5 + payload_len + 2 # Preamble (1) + Device (1) + Length (1) + ID1 (1) + ID2 (1) + Payload (X) + CRC (2)
                    
                    # Read the rest of the message
                    # Ensure we don't try to read more bytes than available or expected
                    bytes_to_read = full_message_len - len(response_buffer)
                    if bytes_to_read > 0:
                        remaining_message = self.__ser.read(bytes_to_read)
                        response_buffer += remaining_message
                    
                    # Check if we have the full message before parsing
                    if len(response_buffer) == full_message_len:
                        self.logger.debug(f'Received raw: {response_buffer.hex()}')
                        parsed_message = self.parse(response_buffer)
                        if parsed_message:
                            return parsed_message
                        else:
                            self.logger.warning(f"Failed to parse received message: {response_buffer.hex()}")
                            response_buffer = b'' # Reset buffer on parse error
                    else:
                        self.logger.debug(f"Partial message received (expected {full_message_len}, got {len(response_buffer)}): {response_buffer.hex()}")
                        response_buffer = b'' # Incomplete message, discard and wait for next preamble
                elif response_buffer: # If we started receiving but no AA, reset
                    response_buffer = b''
            time.sleep(0.01) # Small delay to prevent busy-waiting
        return None

    def __connect(self):
        if self.serial_num:
            try:
                # This part is mostly for Linux and will not work on Windows
                import glob
                link_path_pattern = f"/dev/serial/by-id/*{self.serial_num}*"
                matching_links = glob.glob(link_path_pattern)
                if matching_links:
                    self.port = matching_links[0]
                    self.logger.info(f"Found serial adapter by ID '{self.serial_num}' at '{self.port}'")
                else:
                    self.logger.error(f"No serial adapter found with serial number containing '{self.serial_num}'! Will retry.")
                    time.sleep(5)
                    return # Exit to retry connection
            except Exception as e:
                self.logger.error(f"Error while searching for serial device by ID: {e}")
                time.sleep(5)
                return

        if self.port:
            try:
                self.__ser = serial.Serial(
                    self.port, 
                    self.baudrate, 
                    bytesize=serial.EIGHTBITS, 
                    parity=serial.PARITY_NONE, 
                    stopbits=serial.STOPBITS_ONE, 
                    timeout=0.1, # Short read timeout for non-blocking reads
                    write_timeout=0.5
                )
                self.__ser.reset_input_buffer()
                self.__connected = True
                self.logger.info(f"Serial connection to '{self.port}' established.")
                # Perform initialization sequence
                self._heater_initialization()
            except serial.serialutil.SerialException as e:
                self.logger.critical(f"Cannot connect to serial port '{self.port}': {e}. Will retry.")
                time.sleep(5)
            except Exception as e:
                self.logger.critical(f"Unexpected error during serial connection: {e}")
                time.sleep(5)

    def __disconnect(self):
        if self.__ser and self.__ser.is_open:
            self.__ser.close()
            self.logger.info(f"Disconnected from serial port '{self.port}'.")
        self.__connected = False

    def __reconnect(self):
        self.__disconnect()
        while not self.__connected:
            self.logger.info("Attempting to reconnect...")
            self.__connect()

    def __start_working(self):
        self.__working = True
        self.__worker_thread = threading.Thread(target=self.__worker_thread_run, daemon=True)
        self.__worker_thread.start()

    def __stop_working(self):
        self.__working = False
        if self.__worker_thread.is_alive():
            self.__worker_thread.join(timeout=2)
            if self.__worker_thread.is_alive():
                self.logger.warning("Worker thread did not terminate gracefully.")

    def __worker_thread_run(self):
        self.logger.info('Worker thread started.')
        while self.__working:
            if not self.__connected:
                self.__reconnect()
                time.sleep(1) # Give it a moment before trying to read again
                continue

            try:
                if self.__ser and self.__ser.in_waiting > 0:
                    raw_byte = self.__ser.read(1)
                    if raw_byte == b'\xaa':
                        # A message might be starting
                        remaining_header = self.__ser.read(2)
                        if len(remaining_header) == 2:
                            payload_len = remaining_header[1]
                            # 1 (preamble) + 1 (device) + 1 (length) + 1 (id1) + 1 (id2) + payload_len + 2 (crc)
                            full_message_len = 1 + 1 + 1 + 1 + 1 + payload_len + 2 
                            
                            current_read_len = 1 + len(remaining_header) 
                            remaining_to_read = full_message_len - current_read_len
                            
                            # Read the rest of the message
                            if remaining_to_read > 0:
                                message_bytes = raw_byte + remaining_header + self.__ser.read(remaining_to_read)
                            else:
                                message_bytes = raw_byte + remaining_header # No payload, just header and CRC
                            
                            if len(message_bytes) == full_message_len: # Check if we have a full message
                                parsed_msg = self.parse(message_bytes)
                                if parsed_msg:
                                    self._process_incoming_message(parsed_msg)
                                else:
                                    self.logger.warning(f"Worker: Failed to parse potential message: {message_bytes.hex()}")
                            else:
                                self.logger.warning(f"Worker: Partial message received (expected {full_message_len}, got {len(message_bytes)}): {message_bytes.hex()}")
                        else:
                            self.logger.warning("Worker: Partial header read after preamble.")
                    # else:
                        # self.logger.debug(f"Worker: Discarding non-preamble byte: {raw_byte.hex()}")
                        # pass # Discard single non-preamble bytes
            except serial.serialutil.SerialException as e:
                self.logger.error(f"Worker thread serial error: {e}")
                self.__connected = False
            except Exception as e:
                self.logger.error(f"Worker thread unexpected error: {e}")
            
            time.sleep(0.05) # Prevent busy-waiting

    def _heater_initialization(self):
        self.logger.info("Performing heater initialization sequence...")
        # Send 0x1b multiple times
        for _ in range(12):
            self.__write_message(b'\x1b')
            time.sleep(0.05) # Small delay between 0x1b bytes

        # Sequence from messages_controller.md:
        # C >> H aa 03 00 00 1c | 95 3d
        self.send_and_receive(self.build(0x03, 0x1c), expected_response_type=0x1c, response_device=0x04) # Heater should respond to this usually
        # C >> H aa 03 00 00 04 | 9f 3d (0x04 is an unknown command, might be for older heaters or different mode)
        # self.send_and_receive(self.build(0x03, 0x04)) # Not explicitly in your doc, removing for clarity
        # C >> H aa 03 00 00 06 | 5e bc (version request)
        self.send_and_receive(self.build(0x03, 0x06), expected_response_type=0x06)
        self.send_and_receive(self.build(0x03, 0x06), expected_response_type=0x06) # Sent twice in example
        
        self.logger.info("Heater initialization sequence complete.")

    def _parse_temp(self, byte_val):
        """Helper to parse temperature byte as per documentation."""
        if byte_val > 127:
            return byte_val - 256 # Corrected: temp - 256 for negative numbers
        return byte_val

    def _process_incoming_message(self, message: Message):
        # This is where you would update internal state based on heater responses
        # For this debugging script, we'll mostly print them.
        self.logger.info(f"Processed Heater Message (Device: {message.device:#04x}, Type: {message.msg_id2:#04x}, Payload: {message.payload.hex()})")
        
        if message.device == 0x04: # Heater response
            if message.msg_id2 == 0x0f: # Get status response
                if len(message.payload) == 19: # 0F message has 19 bytes payload
                    status1 = message.payload[0]
                    status2 = message.payload[1]
                    self.__heater_state['status_code'] = (status1, status2)
                    self.__heater_state['status_description'] = status_text.get((status1, status2), 'Unknown Status')
                    self.__heater_state['internal_temp'] = self._parse_temp(message.payload[3])
                    self.__heater_state['external_temp'] = self._parse_temp(message.payload[4])
                    # Byte 5 is skipped
                    self.__heater_state['voltage_mv'] = message.payload[6] * 100 # Documentation says voltage / 10, so * 10 here for V, then *100 for mV
                    self.__heater_state['heater_temp'] = message.payload[8] - 15
                    self.__heater_state['fan_rpm_set'] = message.payload[11] * 60
                    self.__heater_state['fan_rpm_actual'] = message.payload[12] * 60
                    self.__heater_state['fuel_pump_freq'] = message.payload[14] / 100 # freq / 100
                    
                    self.logger.info(f"  Heater Status: {self.__heater_state['status_description']}")
                    self.logger.info(f"    Internal Temp: {self.__heater_state['internal_temp']} C")
                    self.logger.info(f"    External Temp: {self.__heater_state['external_temp']} C")
                    self.logger.info(f"    Heater Temp: {self.__heater_state['heater_temp']} C")
                    self.logger.info(f"    Voltage: {self.__heater_state['voltage_mv']/1000:.1f} V")
                    self.logger.info(f"    Fan RPM (Set/Actual): {self.__heater_state['fan_rpm_set']}/{self.__heater_state['fan_rpm_actual']}")
                    self.logger.info(f"    Fuel Pump Freq: {self.__heater_state['fuel_pump_freq']:.2f} Hz")

                else:
                    self.logger.warning(f"  Status payload length mismatch: Expected 19, Got {len(message.payload)}")
            
            elif message.msg_id2 == 0x02: # Get/set settings response
                if len(message.payload) >= 6:
                    self.__heater_settings['use_work_time'] = "No" if message.payload[0] == 0x01 else "Yes"
                    self.__heater_settings['work_time'] = message.payload[1] # Unclear if this is in minutes, hours etc.
                    self.__heater_settings['temp_source'] = temp_source_text.get(message.payload[2], 'Unknown')
                    self.__heater_settings['temperature_setpoint'] = message.payload[3]
                    self.__heater_settings['wait_mode'] = "On" if message.payload[4] == 0x01 else "Off" if message.payload[4] == 0x02 else "Unknown"
                    self.__heater_settings['level'] = message.payload[5] # 0-9
                    
                    self.logger.info(f"  Heater Settings:")
                    self.logger.info(f"    Use Work Time: {self.__heater_settings['use_work_time']}")
                    self.logger.info(f"    Work Time: {self.__heater_settings['work_time']}")
                    self.logger.info(f"    Temperature Source: {self.__heater_settings['temp_source']}")
                    self.logger.info(f"    Temperature Setpoint: {self.__heater_settings['temperature_setpoint']} C")
                    self.logger.info(f"    Wait Mode: {self.__heater_settings['wait_mode']}")
                    self.logger.info(f"    Level (Power/Fan): {self.__heater_settings['level']}")
                else:
                    self.logger.warning(f"  Settings payload length mismatch: Expected at least 6, Got {len(message.payload)}")

            elif message.msg_id2 == 0x01: # Turn heater on response (shares payload format with settings)
                # The response payload for turn_on_heater is the same format as get_settings
                if len(message.payload) >= 6:
                    self.logger.info(f"  Heater ON Acknowledged (Payload suggests current settings):")
                    self.logger.info(f"    Use Work Time: {'No' if message.payload[0] == 0x01 else 'Yes'}")
                    self.logger.info(f"    Work Time: {message.payload[1]}")
                    self.logger.info(f"    Temperature Source: {temp_source_text.get(message.payload[2], 'Unknown')}")
                    self.logger.info(f"    Temperature Setpoint: {message.payload[3]} C")
                    self.logger.info(f"    Wait Mode: {'On' if message.payload[4] == 0x01 else 'Off' if message.payload[4] == 0x02 else 'Unknown'}")
                    self.logger.info(f"    Level (Power/Fan): {message.payload[5]}")
                else:
                    self.logger.warning(f"  Turn Heater ON payload length mismatch: Expected at least 6, Got {len(message.payload)}")
            
            elif message.msg_id2 == 0x03: # Turn heater/fan off response
                self.logger.info("  Heater/Fan OFF Acknowledged.")

            elif message.msg_id2 == 0x06: # Get version response
                if len(message.payload) == 5:
                    version = ".".join(map(str, message.payload[0:4]))
                    blackbox_version = message.payload[4]
                    self.logger.info(f"  Heater Version: {version}, Blackbox Version: {blackbox_version}")
                else:
                    self.logger.warning(f"  Version payload length mismatch: Expected 5, Got {len(message.payload)}")
            
            elif message.msg_id2 == 0x11: # Set temperature response
                if len(message.payload) == 1:
                    panel_temp = message.payload[0]
                    self.logger.info(f"  Panel Temperature Reported/Set: {panel_temp} C")
                else:
                    self.logger.warning(f"  Set Temperature payload length mismatch: Expected 1, Got {len(message.payload)}")
            
            elif message.msg_id2 == 0x23: # Turn only fan on response
                if len(message.payload) >= 4:
                    level = message.payload[2]
                    self.logger.info(f"  Ventilation ON Acknowledged (Level: {level})")
                else:
                    self.logger.warning(f"  Ventilation ON payload length mismatch: Expected at least 4, Got {len(message.payload)}")

        elif message.device == 0x02 and message.msg_id2 == 0x01: # Diagnostic message ( Heater reports diagnostic data to PC )
            if len(message.payload) == 72:
                self.__diagnostic_data['status1'] = message.payload[0]
                self.__diagnostic_data['status2'] = message.payload[1]
                self.__diagnostic_data['defined_rpm'] = message.payload[11]
                self.__diagnostic_data['measured_rpm'] = message.payload[12]
                self.__diagnostic_data['chamber_temp'] = int.from_bytes(message.payload[18:20],'big')
                self.__diagnostic_data['flame_temp'] = int.from_bytes(message.payload[20:22],'big')
                self.__diagnostic_data['external_temp'] = message.payload[24]
                self.__diagnostic_data['heater_temp'] = message.payload[25]
                self.__diagnostic_data['battery_voltage'] = message.payload[27] / 10
                self.logger.debug(f"Updated diagnostic data: {self.__diagnostic_data}")

    def send_and_receive(self, outgoing_message: bytes, expected_response_type: int = None, response_device: int = 0x04, timeout=2.0, num_retries=3):
        """
        Sends a message and waits for a response.
        :param outgoing_message: The raw bytes of the message to send.
        :param expected_response_type: The msg_id2 of the expected response message. If None, any valid parsed message is returned.
        :param response_device: The device ID of the expected response (default 0x04 for heater responses).
        :param timeout: How long to wait for a response after sending.
        :param num_retries: How many times to retry sending if no valid response is received.
        :return: The parsed Message object if successful, None otherwise.
        """
        for attempt in range(num_retries):
            self.logger.info(f"Attempt {attempt + 1}: Sending {outgoing_message.hex()}")
            if self.__write_message(outgoing_message):
                response = self.__read_response(timeout)
                if response:
                    # Check if the response matches expected type and device
                    if response.device == response_device and (expected_response_type is None or response.msg_id2 == expected_response_type):
                        self.logger.info(f"Received expected response: {response.payload.hex()}")
                        self._process_incoming_message(response)
                        return response
                    else:
                        self.logger.warning(f"Received unexpected response (Dev:{response.device:#04x} Type:{response.msg_id2:#04x}). Expected (Dev:{response_device:#04x} Type:{expected_response_type if expected_response_type is not None else 'any':#04x}): {response.payload.hex()}")
                else:
                    self.logger.warning("No response received.")
            else:
                self.logger.error("Failed to write message.")
                if not self.__connected:
                    self.__reconnect() # Attempt to reconnect if write failed due to disconnection
            time.sleep(0.5) # Wait before retrying
        self.logger.error(f"Failed to get a valid response after {num_retries} attempts.")
        return None

    # Heater control methods (these build and send messages)
    def turn_on_heater(self, mode, setpoint=0x0f, ventilation=0x00, power=0x00, timer=None):
        # The payload structure for 0x01 (turn on) and 0x02 (set settings) are similar according to your doc.
        # However, your `heat` command in `debug_heater.py` doesn't provide all 6 bytes.
        # We need to ensure the payload matches the 6 bytes defined for 'Get/set settings'
        # [use_work_time, work_time, temp_source, temperature_setpoint, wait_mode, level]
        # For 'heat', mode (temp/power) maps to 'temp_source', value maps to 'temperature_setpoint' or 'level'.
        
        # Let's map your debug_heater.py's heat command parameters to the 0x01 payload structure.
        # Assuming:
        # payload[0] = 0x01 (use work time: no)
        # payload[1] = 0x00 (work time: 0)
        # payload[2] = mode (2 for temp, 4 for power)
        # payload[3] = setpoint (if mode is temp) or a default if mode is power
        # payload[4] = 0x00 (wait mode: off)
        # payload[5] = power (if mode is power) or a default if mode is temp

        use_work_time_byte = 0x01 # No work time by default
        work_time_byte = 0x00 # 0 work time by default
        wait_mode_byte = 0x00 # Wait mode off by default

        if mode == 4: # By power
            temp_source_byte = 0x04 # No automatic temp control
            setpoint_byte = 0x0F # Default, heater will ignore if mode 0x04
            level_byte = power # power is the level
        elif mode == 2: # By controller temperature
            temp_source_byte = 0x02 # Panel sensor (set temp message)
            setpoint_byte = setpoint # setpoint is the temperature
            level_byte = 0x00 # Default, heater will use internal calc
        else:
            self.logger.warning(f"Unsupported mode {mode} for turn_on_heater. Defaulting to power mode.")
            temp_source_byte = 0x04
            setpoint_byte = 0x0F
            level_byte = power

        # Reconstruct payload to be 6 bytes long based on 'Get/set settings'
        payload = use_work_time_byte.to_bytes(1, 'big') + \
                  work_time_byte.to_bytes(1, 'big') + \
                  temp_source_byte.to_bytes(1, 'big') + \
                  setpoint_byte.to_bytes(1, 'big') + \
                  wait_mode_byte.to_bytes(1, 'big') + \
                  level_byte.to_bytes(1, 'big')
        
        message = self.build(0x03, 0x01, payload=payload)
        return self.send_and_receive(message, expected_response_type=0x01)

    def shutdown_heater(self):
        message = self.build(0x03, 0x03)
        return self.send_and_receive(message, expected_response_type=0x03)

    def turn_on_ventilation(self, power, timer=None): # Added timer for consistency, but not used in current payload
        # Payload for 0x23: FF FF level FF
        payload = b'\xff\xff' + power.to_bytes(1, byteorder='big') + b'\xff'
        message = self.build(0x03, 0x23, payload=payload)
        return self.send_and_receive(message, expected_response_type=0x23)
    
    def report_controller_temperature(self, temperature):
        payload = temperature.to_bytes(1, byteorder='big')
        message = self.build(0x03, 0x11, payload=payload)
        return self.send_and_receive(message, expected_response_type=0x11)

    def request_status(self):
        message = self.build(0x03, 0x0f)
        return self.send_and_receive(message, expected_response_type=0x0f)

    def request_settings(self):
        message = self.build(0x03, 0x02)
        return self.send_and_receive(message, expected_response_type=0x02)
    
    def set_settings(self, mode, setpoint=0x0f, ventilation=0x00, power=0x00):
        # Similar to turn_on_heater, reconstruct the 6-byte payload
        use_work_time_byte = 0x01 # No work time by default
        work_time_byte = 0x00 # 0 work time by default
        wait_mode_byte = 0x00 # Wait mode off by default

        if mode == 4: # By power
            temp_source_byte = 0x04 # No automatic temp control
            setpoint_byte = 0x0F # Default, heater will ignore if mode 0x04
            level_byte = power # power is the level
        elif mode == 2: # By controller temperature
            temp_source_byte = 0x02 # Panel sensor (set temp message)
            setpoint_byte = setpoint # setpoint is the temperature
            level_byte = 0x00 # Default, heater will use internal calc
        else:
            self.logger.warning(f"Unsupported mode {mode} for set_settings. Defaulting to power mode.")
            temp_source_byte = 0x04
            setpoint_byte = 0x0F
            level_byte = power

        payload = use_work_time_byte.to_bytes(1, 'big') + \
                  work_time_byte.to_bytes(1, 'big') + \
                  temp_source_byte.to_bytes(1, 'big') + \
                  setpoint_byte.to_bytes(1, 'big') + \
                  wait_mode_byte.to_bytes(1, 'big') + \
                  level_byte.to_bytes(1, 'big')
        
        message = self.build(0x03, 0x02, payload=payload)
        return self.send_and_receive(message, expected_response_type=0x02)

    def diagnostic_mode_on(self):
        message = self.build(0x03, 0x07, payload=b'\x01')
        return self.send_and_receive(message, expected_response_type=0x07) # Heater typically responds with empty payload for 0x07

    def diagnostic_mode_off(self):
        message = self.build(0x03, 0x07, payload=b'\x00')
        return self.send_and_receive(message, expected_response_type=0x07)
        
    def get_heater_state(self):
        # This would be updated by the worker thread's _process_incoming_message
        return self.__heater_state

    def get_diagnostic_data(self):
        # This would be updated by the worker thread's _process_incoming_message
        return self.__diagnostic_data
    
    def get_heater_settings(self): # New getter for settings
        return self.__heater_settings

    def cleanup(self):
        self.logger.info("Cleaning up AutotermHeaterController...")
        self.__stop_working()
        self.__disconnect()