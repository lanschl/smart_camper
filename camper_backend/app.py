from flask import Flask
from flask_socketio import SocketIO # type: ignore
import atexit
import time
import csv
from datetime import datetime, timedelta
from collections import deque
import logging
from typing import Optional
import json
import os

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


from logging_utils import setup_logging

# --- Logging Setup ---
LOG_DIR = '/home/lukas/smart_camper/camper_backend/logs'

# 1. Setup App/Debug Logging
debug_log_path = setup_logging(LOG_DIR, "debug")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(debug_log_path),
        logging.StreamHandler()
    ]
)


# --- NEW: Global State for Local Runtime Timer (Python-managed timer) ---
# Unix timestamp (seconds) when the initial timer should expire.
HEATER_RUNTIME_END_TIME: Optional[float] = None
# Unix timestamp (seconds) when the final safety shutdown should occur (Node-RED's 5-minute delay).
HEATER_SAFETY_SHUTDOWN_TIME: Optional[float] = None
# Flag to prevent re-sending the initial shutdown command
HEATER_SHUTDOWN_TRIGGERED = False
# Stores the initial duration for UI reporting (in minutes)
HEATER_RUNTIME_DURATION: Optional[int] = None
# --- NEW: Retry timestamp for delayed shutdown (if heater is starting) ---
HEATER_RETRY_SHUTDOWN_TIMESTAMP: Optional[float] = None
# --- NEW: Global State for Weekly Scheduler (Mimics Node-RED's external storage) ---
# NOTE: In a production system, these should be loaded from a persistent storage like a DB or file.
HEATER_SCHEDULE_FILE = '/home/lukas/smart_camper/camper_backend/heater_schedule.json' 
HEATER_TIMER_ON_OFF = False # Mimics the Timer Off/On switch (773d9bfdbb55d26d)
HEATER_SCHEDULE = {
    "timers": [
        # { "starttime": "08:00", "days": [1, 2, 3, 4, 5], "output": 22, "endtime": "09:00" } 
    ]
}

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
# 2. Setup Heater Logging
heater_log_path = setup_logging(LOG_DIR, "heater")
heater_controller = HeaterController(HEATER_CONFIG['serial_number'], heater_log_path)

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

def load_heater_schedule():
    """Placeholder for loading state from a persistent file/DB on startup."""
    global HEATER_SCHEDULE
    try:
        # Assuming HEATER_SCHEDULE_FILE contains the JSON structure
        with open(HEATER_SCHEDULE_FILE, 'r') as f:
            HEATER_SCHEDULE = json.load(f)
        # Note: Loading the HEATER_TIMER_ON_OFF boolean would be done here too
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("Heater schedule file not found or invalid. Starting with empty schedule.")
    except Exception as e:
        logging.error(f"Error loading heater schedule: {e}")

def save_heater_schedule():
    """Placeholder for saving state to a persistent file/DB."""
    global HEATER_SCHEDULE
    try:
        with open(HEATER_SCHEDULE_FILE, 'w') as f:
            json.dump(HEATER_SCHEDULE, f)
    except Exception as e:
        logging.error(f"Error saving heater schedule: {e}")


def check_heater_schedule():
    """Checks the weekly schedule and sends commands if a timer has fired."""
    global HEATER_TIMER_ON_OFF, HEATER_SCHEDULE, HEATER_RETRY_SHUTDOWN_TIMESTAMP

    if not HEATER_TIMER_ON_OFF:
        return # Timer system disabled (matches Node-RED's 'check timer on/off' switch)

    now = datetime.now()
    current_day = now.weekday() # Monday is 0, Sunday is 6
    # Note: Using seconds ensures this only fires once per minute (or less often depending on the loop interval)
    current_time_str_min = now.strftime("%H:%M") 
    current_timestamp = time.time()

    # --- 0. RETRY LOGIC (For delayed shutdowns) ---
    if HEATER_RETRY_SHUTDOWN_TIMESTAMP is not None and current_timestamp >= HEATER_RETRY_SHUTDOWN_TIMESTAMP:
        heater_state = heater_controller.get_state()
        status = heater_state.get('status', 'Standby')
        
        if "Starting" in status:
            logging.warning(f"RETRY SHUTDOWN: Heater still in '{status}'. Deferring for another 60s.")
            HEATER_RETRY_SHUTDOWN_TIMESTAMP = current_timestamp + 60
        elif "Shutting" in status or status == "Standby" or status == "off":
             logging.info(f"RETRY SHUTDOWN: Heater already '{status}'. Retry cleared.")
             HEATER_RETRY_SHUTDOWN_TIMESTAMP = None
        else:
            logging.info(f"RETRY SHUTDOWN: Heater now in '{status}'. Safe to shutdown. Executing.")
            heater_controller.shutdown()
            HEATER_RETRY_SHUTDOWN_TIMESTAMP = None

    for timer in HEATER_SCHEDULE.get("timers", []):
        days = timer.get("days", [])
        start_time_str = timer.get("starttime")
        end_time_str = timer.get("endtime")

        if current_day in days:
            # --- START TIME LOGIC (Mimics Node-RED's [true] output) ---
            if start_time_str == current_time_str_min:
                # Node-RED timer forces the heater into TempMode at the setpoint stored in 'output'
                setpoint = timer.get("output", 22) 
                
                # Simple check to prevent sending commands repeatedly every 10 seconds
                heater_state = heater_controller.get_state()
                if heater_state.get('mode') != 'temperature' or heater_state.get('setpoint') != setpoint:
                    logging.info(f"SCHEDULE FIRED: Starting Temp Mode to {setpoint}°C.")
                    # The Node-RED scheduler is a fixed time point, not a timed run, so no runtime timer is set here
                    heater_controller.turn_on_heating(
                        mode='temperature', 
                        value=setpoint,
                        run_timer_minutes=None
                    )
                
            # --- END TIME LOGIC (Mimics Node-RED's [false] output) ---
            elif end_time_str == current_time_str_min:
                heater_state = heater_controller.get_state()
                status = heater_state.get('status', 'Standby')
                
                # 1. Safety Check: Don't shut down if starting
                if "Starting" in status:
                    logging.warning(f"SCHEDULE FIRED: Shutdown requested but heater is in '{status}'. Deferring for 60s.")
                    HEATER_RETRY_SHUTDOWN_TIMESTAMP = time.time() + 60
                
                # 2. Redundancy Check: Don't shut down if already off/stopping
                elif "Shutting" in status or status == "Standby" or status == "off":
                    # logging.info(f"SCHEDULE FIRED: Heater already in '{status}'. No action needed.")
                    pass
                
                else:
                    logging.info(f"SCHEDULE FIRED: Shutting down heater (Current status: {status}).")
                    heater_controller.shutdown()

load_heater_schedule() # Call this once on startup

def cleanup_old_boiler_logs():
    """Removes entries older than 24 hours from the boiler log CSV."""
    try:
        cutoff_time = time.time() - (24 * 3600) # 24 hours ago
        rows_to_keep = []
        
        if os.path.exists(TEMPERATURE_LOG_FILE):
            with open(TEMPERATURE_LOG_FILE, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 1:
                        try:
                            # row[0] is timestamp
                            if float(row[0]) > cutoff_time:
                                rows_to_keep.append(row)
                        except ValueError:
                            pass # Skip malformed lines
            
            # Write back only the recent data
            with open(TEMPERATURE_LOG_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows_to_keep)
            
            logging.info(f"Cleaned up boiler log. Kept {len(rows_to_keep)} entries (last 24h).")
    except Exception as e:
        logging.error(f"Error cleaning boiler log: {e}")

# Run cleanup once on startup
cleanup_old_boiler_logs()
boiler_temp_history = load_history_from_log()

# --- NEW: Timer Management function to run in background thread ---
def check_runtime_timer():
    """
    Checks the local timer and triggers the shutdown sequence if it has expired.
    Also handles the second, delayed safety shutdown (Node-RED's 5-minute delay).
    """
    global HEATER_RUNTIME_END_TIME, HEATER_SAFETY_SHUTDOWN_TIME, HEATER_SHUTDOWN_TRIGGERED, HEATER_RUNTIME_DURATION
    
    current_time = time.time()
    
    # --- STEP 1: Check for Initial Shutdown Trigger ---
    if HEATER_RUNTIME_END_TIME is not None and current_time >= HEATER_RUNTIME_END_TIME and not HEATER_SHUTDOWN_TRIGGERED:
        logging.info("RUNTIME TIMER EXPIRED: Triggering initial heater shutdown.")
        heater_controller.shutdown() 
        
        # Set the safety shutdown time for 5 minutes later (Node-RED delay)
        HEATER_SAFETY_SHUTDOWN_TIME = current_time + (5 * 60)
        HEATER_SHUTDOWN_TRIGGERED = True
        
        # Clear the runtime timer so it doesn't fire again
        HEATER_RUNTIME_END_TIME = None 

    # --- STEP 2: Check for Safety Shutdown Trigger (5m delay) ---
    if HEATER_SAFETY_SHUTDOWN_TIME is not None and current_time >= HEATER_SAFETY_SHUTDOWN_TIME:
        logging.info("SAFETY SHUTDOWN TIMER EXPIRED: Sending secondary shutdown command.")
        # Node-RED: Triggers the final delayed stop
        heater_controller.shutdown() 
        
        # Clear all state variables
        HEATER_SAFETY_SHUTDOWN_TIME = None
        HEATER_RUNTIME_DURATION = None
        HEATER_SHUTDOWN_TRIGGERED = False

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
    global HEATER_RUNTIME_END_TIME, HEATER_SAFETY_SHUTDOWN_TIME
    
    print("Starting sensor reading background thread.")
    last_cleanup_time = time.time()
    
    while True:
        # --- NEW: Periodic Log Cleanup (Every Hour) ---
        if time.time() - last_cleanup_time > 3600:
            cleanup_old_boiler_logs()
            last_cleanup_time = time.time()

        # --- NEW: Check local runtime timer ---
        check_runtime_timer()
        
        # --- NEW: Check weekly schedule ---
        check_heater_schedule()
        
        # 1. Read local sensors
        sensor_data = sensor_reader.read_all_sensors()

        # 2. Read water level sensors, BMS data... (remains the same)
        water_levels = water_level_controller.read_levels()
        sensor_data.update(water_levels)
        bms_data = bms_reader.read_data()
        if bms_data:
            sensor_data.update(bms_data)

        # 3. Feed the cabin temp to the heater controller
        inside_temp = sensor_data.get('insideTemp')
        if inside_temp is not None:
            heater_controller.update_cabin_temperature(inside_temp)
            
        # 4. Get the latest full state from the heater 
        heater_state = heater_controller.get_state()
        
        if heater_state:
            if inside_temp:
                heater_state['readings']['panelTemp'] = inside_temp
            
            # --- MODIFIED: Override the timer display with local countdown ---
            local_remaining_minutes = None
            current_time = time.time()
            
            if HEATER_RUNTIME_END_TIME is not None:
                 # Timer is actively running toward the end time
                 local_remaining_minutes = max(0, int((HEATER_RUNTIME_END_TIME - current_time) / 60))
            elif HEATER_SAFETY_SHUTDOWN_TIME is not None:
                # Timer expired, we are in the 5-minute cooldown/safety period. Display 0.
                local_remaining_minutes = 0

            if local_remaining_minutes is not None:
                # Override the hardware controller's timer state for accurate UI countdown
                heater_state['timer'] = local_remaining_minutes
            elif HEATER_RUNTIME_DURATION is not None and HEATER_SAFETY_SHUTDOWN_TIME is None:
                # This state means the timer expired, shutdown was triggered, but the safety check hasn't run yet.
                heater_state['timer'] = 0
            
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

# --- NEW: SocketIO handler for controlling the persistent scheduler ---
@socketio.on('diesel_heater_schedule_command')
def handle_diesel_heater_schedule_command(data):
    """
    Handles commands for the persistent weekly schedule (e.g., setting the timers from UI).
    e.g., {'command': 'set_timer_toggle', 'value': True}
    e.g., {'command': 'set_schedule', 'schedule': [{...}]}
    """
    global HEATER_TIMER_ON_OFF, HEATER_SCHEDULE
    command = data.get('command')
    
    if command == 'set_timer_toggle':
        # Mimics the "Timer Off/On" switch in Node-RED
        HEATER_TIMER_ON_OFF = data.get('value', False)
        logging.info(f"Heater Weekly Timer System toggled to: {HEATER_TIMER_ON_OFF}")
        
    elif command == 'set_schedule':
        # Mimics the saving of the schedule after being edited
        new_schedule = data.get('schedule')
        if isinstance(new_schedule, list):
            HEATER_SCHEDULE["timers"] = new_schedule
            logging.info(f"Heater schedule updated with {len(new_schedule)} entries.")
            save_heater_schedule() # Save to persistence
        else:
            logging.error("Invalid schedule format received (expected a list).")

    elif command == 'get_schedule':
        # Send the current schedule back to the client
        socketio.emit('schedule_update', {
            'timers': HEATER_SCHEDULE.get("timers", []),
            'isEnabled': HEATER_TIMER_ON_OFF
        })

@socketio.on('diesel_heater_command')
def handle_diesel_heater_command(data):
    """
    Handles all commands for the diesel heater.
    If 'run_timer_minutes' is present, it starts the Python-managed local timer.
    """
    global HEATER_RUNTIME_END_TIME, HEATER_SAFETY_SHUTDOWN_TIME, HEATER_RUNTIME_DURATION, HEATER_SHUTDOWN_TRIGGERED
    
    command = data.get('command')
    logging.info(f"Received diesel_heater_command: {data}")
    
    # --- SHUTDOWN / RESET LOGIC ---
    if command == 'shutdown':
        # Node-RED Stop button logic: Stops the heater AND resets the timer.
        heater_controller.shutdown()
        
        HEATER_RUNTIME_END_TIME = None
        HEATER_SAFETY_SHUTDOWN_TIME = None
        HEATER_RUNTIME_DURATION = None
        HEATER_SHUTDOWN_TRIGGERED = False
        
    # --- START/TURN ON LOGIC ---
    elif command == 'turn_on' or command == 'turn_on_ventilation':
        mode = data.get('mode')
        value = data.get('value')
        run_timer_minutes = data.get('run_timer_minutes')
        
        if run_timer_minutes is not None and run_timer_minutes > 0:
            # --- START TIMED RUN (Python-Managed) ---
            minutes = int(run_timer_minutes)
            logging.info(f"Starting Python-managed timed run for {minutes} minutes.")
            
            # Set the local timer state
            HEATER_RUNTIME_END_TIME = time.time() + (minutes * 60)
            HEATER_RUNTIME_DURATION = minutes
            HEATER_SAFETY_SHUTDOWN_TIME = None
            HEATER_SHUTDOWN_TRIGGERED = False
            
            # Send the ON command *without* setting the internal hardware timer
            # Note: We pass run_timer_minutes=None here to tell the heater controller
            # to rely on Python for the shutdown.
            if command == 'turn_on':
                heater_controller.turn_on_heating(mode, value, run_timer_minutes=None)
            else:
                heater_controller.turn_on_ventilation(value, run_timer_minutes=None)
        
        else:
            # --- START INDEFINITE RUN ---
            # Clear local timer and run indefinitely (Python will not interfere)
            HEATER_RUNTIME_END_TIME = None
            HEATER_SAFETY_SHUTDOWN_TIME = None
            HEATER_RUNTIME_DURATION = None
            HEATER_SHUTDOWN_TRIGGERED = False

            if command == 'turn_on':
                heater_controller.turn_on_heating(mode, value, run_timer_minutes=None)
            else:
                heater_controller.turn_on_ventilation(value, run_timer_minutes=None)
        
    # --- CHANGE SETTING LOGIC ---
    elif command == 'change_setting':
        # Allows for changing mode/value while a timer is running (Python or Hardware-managed)
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