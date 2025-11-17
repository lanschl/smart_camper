import autotherm_heater # Assuming autoterm_heater.py is in the same directory
import time
import logging

# --- Configuration for your USB-to-UART adapter ---
# IMPORTANT: Replace with YOUR device's serial number or port path
# You can find the serial number using `ls -l /dev/serial/by-id/`
# Or the direct port path using `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
SERIAL_NUMBER = None # e.g., 'A50285BI' or 'FTDI_FT232R_USB_UART_ABSCHPJ4'
# Or, if you prefer direct port path:
# SERIAL_PORT_PATH = '/dev/ttyUSB0' 
# Leave SERIAL_NUMBER as None if using SERIAL_PORT_PATH
SERIAL_PORT_PATH = 'COM3' 

# --- Initialize the controller ---
# If using SERIAL_NUMBER, pass serial_num. Otherwise, pass serial_port.
if SERIAL_NUMBER:
    heater_controller = autotherm_heater.AutotermHeaterController(
        serial_num=SERIAL_NUMBER,
        baudrate=9600,
        log_level=logging.INFO # Set to DEBUG for very verbose output
    )
elif SERIAL_PORT_PATH:
    heater_controller = autotherm_heater.AutotermHeaterController(
        serial_port=SERIAL_PORT_PATH,
        baudrate=9600,
        log_level=logging.INFO
    )
else:
    print("ERROR: Please configure SERIAL_NUMBER or SERIAL_PORT_PATH in debug_heater.py")
    exit()

try:
    print("\n--- Autoterm Heater Debugger ---")
    print("Available commands:")
    print("  status        - Request heater status")
    print("  settings      - Request heater settings")
    print("  temp [C]      - Report controller temperature (e.g., 'temp 20')")
    print("  heat [mode] [value] [timer_min] - Turn on heater (e.g., 'heat power 5 60' or 'heat temp 22')")
    print("                        modes: 'power', 'temp'")
    print("  vent [level] [timer_min] - Turn on ventilation (e.g., 'vent 7 30')")
    print("  set [mode] [value] - Change current heater settings (e.g., 'set power 6')")
    print("  shutdown      - Turn off heater")
    print("  diag on       - Turn on diagnostic mode")
    print("  diag off      - Turn off diagnostic mode")
    print("  state         - Print last known heater state")
    print("  dstate        - Print last known diagnostic data")
    print("  exit          - Exit the debugger")
    print("--------------------------------\n")

    while True:
        command = input("Enter command: ").strip().lower()

        if command == 'exit':
            break
        elif command == 'status':
            heater_controller.request_status()
        elif command == 'settings':
            heater_controller.request_settings()
        elif command.startswith('temp '):
            try:
                temp = int(command.split(' ')[1])
                heater_controller.report_controller_temperature(temp)
            except (IndexError, ValueError):
                print("Usage: temp [C]")
        elif command.startswith('heat '):
            parts = command.split(' ')
            if len(parts) >= 3:
                mode = parts[1]
                try:
                    value = int(parts[2])
                    timer_min = int(parts[3]) if len(parts) > 3 else None
                    mode_code = 0 # Default to "by power"
                    setpoint = 0
                    power = 0
                    if mode == 'power':
                        mode_code = 4 # By power
                        power = value
                    elif mode == 'temp':
                        mode_code = 2 # By controller temperature
                        setpoint = value
                    else:
                        print("Invalid heat mode. Use 'power' or 'temp'.")
                        continue
                    
                    heater_controller.turn_on_heater(mode=mode_code, setpoint=setpoint, power=power, timer=timer_min)
                except (IndexError, ValueError):
                    print("Usage: heat [mode] [value] [timer_min, optional]")
            else:
                print("Usage: heat [mode] [value] [timer_min, optional]")
        elif command.startswith('vent '):
            parts = command.split(' ')
            if len(parts) >= 2:
                try:
                    level = int(parts[1])
                    timer_min = int(parts[2]) if len(parts) > 2 else None
                    heater_controller.turn_on_ventilation(power=level, timer=timer_min)
                except (IndexError, ValueError):
                    print("Usage: vent [level] [timer_min, optional]")
            else:
                print("Usage: vent [level] [timer_min, optional]")
        elif command.startswith('set '):
            parts = command.split(' ')
            if len(parts) >= 3:
                mode = parts[1]
                try:
                    value = int(parts[2])
                    mode_code = 0 
                    setpoint = 0
                    power = 0
                    if mode == 'power':
                        mode_code = 4 # By power
                        power = value
                    elif mode == 'temp':
                        mode_code = 2 # By controller temperature
                        setpoint = value
                    else:
                        print("Invalid set mode. Use 'power' or 'temp'.")
                        continue
                    heater_controller.set_settings(mode=mode_code, setpoint=setpoint, power=power)
                except (IndexError, ValueError):
                    print("Usage: set [mode] [value]")
            else:
                print("Usage: set [mode] [value]")
        elif command == 'shutdown':
            heater_controller.shutdown_heater()
        elif command == 'diag on':
            heater_controller.diagnostic_mode_on()
        elif command == 'diag off':
            heater_controller.diagnostic_mode_off()
        elif command == 'state':
            print("Current Heater State:")
            print(heater_controller.get_heater_state())
        elif command == 'dstate':
            print("Current Diagnostic Data:")
            print(heater_controller.get_diagnostic_data())
        else:
            print("Unknown command. Type 'help' for options.")

except KeyboardInterrupt:
    print("\nExiting debugger.")
finally:
    heater_controller.cleanup()
    print("Cleanup complete.")