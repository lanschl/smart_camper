# config.py

# GPIO pin numbers (BCM numbering scheme) for the drain valves
VALVE_PINS = {
    # This ID must match the 'id' from your React App's initialVanState
    'gray_drain': 17,
    'fresh_winter_drain': 27,
    'shower_drain': 22,
    # You can add the 4th relay here later if you use it
}

# Network configuration for the server
SERVER_HOST = '0.0.0.0' # Listen on all network interfaces
SERVER_PORT = 5000


# Configuration for the ESP32-based PWM Light Controller
ESP32_LIGHT_CONFIG = {
    # Find this with 'ls /dev/tty*' - usually ttyACM0 or ttyUSB0
    'port': '/dev/ttyUSB0', 
    'pins': {
        # These IDs MUST match the IDs in the ESP32's main.py script
        'deko': 12,
        'ambiente': 14,
        'ceiling': 13,
    }
}


# GPIO pins (BCM numbering) for simple on/off pumps via MOSFETs
PUMP_PINS = {
    'fresh_pump': 23,
    'hot_pump': 24,
}

# GPIO pins for momentary pulse actuators like drawer locks
# One logical device maps to two pins: one for lock, one for unlock
ACTUATOR_PINS = {
    'drawers': {
        'lock_pin': 20,
        'unlock_pin': 21,
    }
}

# GPIO pin for the boiler's Solid State Relay (SSR)
BOILER_PINS = {
    'boiler_heat': 25,
}

# GPIO pin for the PWM-controlled heated floors
FLOOR_HEATING_PINS = {
    'floor_heat': 16,
}

SENSOR_IDS = {
    'insideTemp': '8441cd1e64ff',
    'boilerTemp': '3ce1d443b7d1',
    # 'outsideTemp': '00000b4a557e',
}

WATER_SENSOR_CONFIG = {
    'freshWater': {
        'sensors': {
            # 'fresh_1': {'trigger_pin': 5, 'echo_pin': 6},
            # 'fresh_2': {'trigger_pin': 19, 'echo_pin': 26},
        },
        # Calibration: Distance in CM from sensor to water surface
        'dist_full': 20,  # The distance reading (cm) when the tank is 100% full
        'dist_empty': 59, # The distance reading (cm) when the tank is 0% full
    },
    'grayWater': {
        'sensors': {
            # 'gray_1': {'trigger_pin': 8, 'echo_pin': 7},
        },
        # Calibration for the "hack"
        'dist_full': 20,   # Sensor's minimum reading distance
        'dist_empty': 25,  # The actual height of your tank
        'full_override_threshold': 60, # If reading jumps above this, assume it's full
    }
}

BMS_MAC_ADDRESS = "C8:8C:07:04:29:4B"
BMS_PROTOCOL = "JK02_32"


HEATER_CONFIG = {
    'serial_number': 'FTDI_FT232R_USB_UART_ABSCHPJ4',   # serial number you can find with this command:  ls -l /dev/serial/by-id/
    'log_path': '/home/lukas/smart_camper/camper_backend/heater.log',
}
