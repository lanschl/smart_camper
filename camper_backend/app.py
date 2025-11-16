from flask import Flask
from flask_socketio import SocketIO # type: ignore
import atexit
import time
import csv
from datetime import datetime, timedelta
from collections import deque
import logging

from config import (VALVE_PINS, ESP32_LIGHT_CONFIG, PUMP_PINS, ACTUATOR_PINS, SERVER_HOST, 
                    SERVER_PORT, BOILER_PINS, FLOOR_HEATING_PINS, SENSOR_IDS, 
                    WATER_SENSOR_CONFIG, BMS_MAC_ADDRESS, BMS_PROTOCOL, HEATER_CONFIG )
from hardware.valves import ValveController
from hardware.lights import LightController
from hardware.pumps import PumpController 
from hardware.actuators import ActuatorController
from hardware.switches import SwitchController
from hardware.pwm_devices import PWMDeviceController
from hardware.sensors import SensorReader
from hardware.water_level import WaterLevelController
from hardware.bms import BMSReader 
from hardware.heater import HeaterController


logging.basicConfig(
    level=logging.INFO,  # <-- CHANGE BACK TO INFO
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("/home/lukas/smart_camper/camper_backend/debug.log"),
        logging.StreamHandler()
    ]
)

# --- Initialization ---
app = Flask(__name__)
# In a real app, you'd want a more secure secret key
app.config['SECRET_KEY'] = 'vanlife!' 

# Allow all origins for easy development. For production, you might restrict this.
socketio = SocketIO(app, cors_allowed_origins="*")


# Initialize our hardware controller with the pins from the config file
valve_controller = ValveController(VALVE_PINS)
light_controller = LightController(ESP32_LIGHT_CONFIG['port'], ESP32_LIGHT_CONFIG['pins'])
pump_controller = PumpController(PUMP_PINS)
actuator_controller = ActuatorController(ACTUATOR_PINS)
boiler_controller = SwitchController(BOILER_PINS)
floor_heating_controller = PWMDeviceController(FLOOR_HEATING_PINS)
sensor_reader = SensorReader(SENSOR_IDS)
water_level_controller = WaterLevelController(WATER_SENSOR_CONFIG)
bms_reader = BMSReader(BMS_MAC_ADDRESS, BMS_PROTOCOL)
heater_controller = HeaterController(HEATER_CONFIG['serial_number'], HEATER_CONFIG['log_path'])

TEMPERATURE_LOG_FILE = '/home/lukas/smart_camper/camper_backend/boiler_temp_log.csv'

def load_history_from_log():
    """Reads the CSV log file and returns the last 12 hours of data."""
    history = deque(maxlen=4320) # Maxlen for 12 hours at 10s intervals
    twelve_hours_ago = datetime.now() - timedelta(hours=12)
    
    try:
        with open(TEMPERATURE_LOG_FILE, 'r', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                # row[0] is timestamp, row[1] is temp
                timestamp_sec = int(row[0])
                log_time = datetime.fromtimestamp(timestamp_sec)
                
                if log_time > twelve_hours_ago:
                    # Convert back to JS-compatible milliseconds for the UI
                    history.append({'time': timestamp_sec * 1000, 'temp': float(row[1])})
        print(f"Loaded {len(history)} historical data points from the last 12 hours.")
    except FileNotFoundError:
        print("Log file not found. Starting with an empty history.")
    except Exception as e:
        print(f"Error loading history from log: {e}")
        
    return history


boiler_temp_history = load_history_from_log()

# --- Web Socket Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """
    This function is called when a new client connects to the server.
    """
    print('React client connected to Python backend!')

@socketio.on('disconnect')
def handle_disconnect():
    """
    This function is called when a client disconnects.
    """
    print('React client disconnected.')

@socketio.on('switch_toggle')
def handle_switch_toggle(data):
    """
    Handles toggling of simple on/off devices like valves and pumps.
    Expected data: {'id': 'gray_drain', 'isOn': True}
    """
    device_id = data.get('id')
    new_state = data.get('isOn')

    print(f"Received 'switch_toggle' event for '{device_id}' -> {new_state}")

    if device_id in valve_controller.pin_config:
        valve_controller.set_valve_state(device_id, new_state)
    elif device_id in pump_controller.pin_config:
        pump_controller.set_pump_state(device_id, new_state)
    elif device_id in actuator_controller.pin_config:
        action = 'lock' if new_state else 'unlock'
        actuator_controller.trigger_actuator(device_id, action)
    elif device_id in boiler_controller.pin_config: 
        boiler_controller.set_state(device_id, new_state)
    else:
        print(f"Warning: No handler for device_id '{device_id}'")

@socketio.on('light_change')
def handle_light_change(data):
    """
    Handles dimming of lights.
    Expected data: {'id': 'deko', 'level': 75}
    """
    device_id = data.get('id')
    new_level = data.get('level')
    logging.info(f"Received 'light_change' event for '{device_id}' -> {new_level}%")

    # This now calls the new controller
    if device_id in light_controller.pin_config:
        light_controller.set_light_level(device_id, new_level)
    else:
        logging.warning(f"Warning: No handler for light_id '{device_id}'")


@socketio.on('floor_heating_change')
def handle_floor_heating_change(data):
    """
    Handles changing the level of the heated floors.
    Expected data: {'id': 'floor_heat', 'level': 40}
    """
    device_id = data.get('id')
    new_level = data.get('level')
    
    if device_id in floor_heating_controller.pin_config:
        floor_heating_controller.set_level(device_id, new_level)
    else:
        print(f"Warning: No handler for floor heating device '{device_id}'")


def sensor_reading_thread():
    """
    Reads sensors, logs boiler temp, checks timers, and pushes updates.
    """
    print("Starting sensor reading background thread.")
    # *** REMOVED: Global timer variables ***
    while True:
        # --- NEW: Check heater timers ---
        # This will automatically trigger start/shutdown if needed
        heater_controller.check_timers()
        
        # 1. Read local sensors
        sensor_data = sensor_reader.read_all_sensors()

        # 2. Read water level sensors
        water_levels = water_level_controller.read_levels()
        sensor_data.update(water_levels)
        bms_data = bms_reader.read_data()
        if bms_data:
            sensor_data.update(bms_data)

        # 3. Feed the cabin temp to the heater controller
        inside_temp = sensor_data.get('insideTemp')
        if inside_temp is not None:
            heater_controller.update_cabin_temperature(inside_temp)
            
        # 4. Get the latest full state from the heater (which now includes timer info)
        heater_state = heater_controller.get_state()
        if heater_state:
            sensor_data['dieselHeater'] = heater_state
        
        # 5. Log boiler temperature
        if sensor_data:
            boiler_temp = sensor_data.get('boilerTemp')
            
            if boiler_temp is not None:
                current_time_sec = int(time.time())
                try:
                    with open(TEMPERATURE_LOG_FILE, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([current_time_sec, boiler_temp])
                except Exception as e:
                    print(f"Error writing to log file: {e}")
                
                current_time_ms = current_time_sec * 1000
                boiler_temp_history.append({'time': current_time_ms, 'temp': boiler_temp})
            
            sensor_data['boilerTempHistory'] = list(boiler_temp_history)

            # 6. Emit the complete package to the UI
            # print(f"Pushing sensor update to UI (history has {len(boiler_temp_history)} points)")
            socketio.emit('sensor_update', sensor_data)
        
        socketio.sleep(10) # 10-second loop

@socketio.on('diesel_heater_command')
def handle_diesel_heater_command(data):
    """
    Handles all commands for the diesel heater.
    e.g., {'command': 'start_in', 'value': 30, 'action': {'command': 'turn_on', 'mode': 'power', 'value': 5, 'run_timer_minutes': 120}}
    e.g., {'command': 'shutdown'}
    e.g., {'command': 'turn_on', 'mode': 'temperature', 'value': 22, 'run_timer_minutes': 60}
    """
    # *** REMOVED: Global timer variables ***
    command = data.get('command')
    logging.info(f"Received diesel_heater_command: {data}")
    
    if command == 'start_in':
        # *** UPDATED: Use controller method ***
        heater_controller.set_start_timer(data.get('value'), data.get('action'))
            
    elif command == 'cancel_start_timer':
        # *** UPDATED: Use controller method ***
        heater_controller.cancel_start_timer()
        
    elif command == 'shutdown':
        heater_controller.shutdown()
        
    elif command == 'turn_on':
        # This now correctly passes the run_timer_minutes
        heater_controller.turn_on_heating(
            data.get('mode'), 
            data.get('value'),
            data.get('run_timer_minutes')
        )
        
    elif command == 'turn_on_ventilation':
        # This now correctly passes the run_timer_minutes
        heater_controller.turn_on_ventilation(
            data.get('value'),
            data.get('run_timer_minutes')
        )
        
    elif command == 'change_setting':
        # Note: This relies on the 'change_settings' method to preserve
        # the existing shutdown timer.
        heater_controller.change_settings(data.get('mode'), data.get('value'))


# --- Main Application ---

def cleanup_on_exit():
    """
    Ensures that all GPIO devices are cleaned up properly when the script exits.
    """
    print("Server is shutting down. Performing cleanup...")
    valve_controller.cleanup()
    light_controller.cleanup()
    pump_controller.cleanup()
    actuator_controller.cleanup()
    boiler_controller.cleanup() 
    floor_heating_controller.cleanup()
    water_level_controller.cleanup()
    bms_reader.cleanup()
    heater_controller.cleanup()
    
     
if __name__ == '__main__':
    atexit.register(cleanup_on_exit)

    socketio.start_background_task(target=sensor_reading_thread)
    
    print(f"Starting campervan server at http://{SERVER_HOST}:{SERVER_PORT}")
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, allow_unsafe_werkzeug=True)