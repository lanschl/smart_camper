# Campervan Control System - Python Backend

This repository contains the complete Python backend for the campervan control system. It serves as the bridge between the React-based frontend UI and all the physical hardware in the van, using Flask-SocketIO for real-time communication.

## System Architecture

The system operates on a simple client-server model running on a single Raspberry Pi:

`React UI (Client)` <--> `WebSockets (Socket.IO)` <--> `Flask App (Server)` <--> `Hardware Controllers` <--> `Physical Devices`

---

## 1. Full System Setup (From a Fresh Debian Install)

This guide covers all steps to provision a new Raspberry Pi to run this project.

### Step 1.1: OS-Level Dependencies

First, update your package lists and install all necessary system-level tools and libraries.

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip swig liblgpio-dev nodejs npm unclutter chromium gsettings-desktop-schemas
```
*   `git`: For version control.
*   `python3-venv`, `python3-pip`: For managing the Python environment.
*   `swig`, `liblgpio-dev`: Required to compile the `lgpio` Python library.
*   `nodejs`, `npm`: Required to build and run the React frontend.
*   `unclutter`, `chromium`, `gsettings-desktop-schemas`: Required for the Kiosk mode UI.

### Step 1.2: Raspberry Pi Hardware Configuration

You must manually enable the hardware peripherals we need. Edit the boot configuration file:

```bash
sudo nano /boot/firmware/config.txt
```
Scroll to the bottom and add the following lines:

```txt
# Enable Hardware PWM for flicker-free light dimming
dtoverlay=pwm-2chan

# Enable the 1-Wire interface for DS18B20 temperature sensors
dtoverlay=w1-gpio
```
Save the file (`Ctrl+O`, `Enter`) and **reboot the Pi** for these changes to take effect:
```bash
sudo reboot
```

### Step 1.3: Python Environment Setup

We use a virtual environment (`venv`) to keep our Python packages isolated and clean.

```bash
# Navigate to your project directory
cd ~/camper_backend

# Create the virtual environment
python3 -m venv .venv

# Activate the virtual environment (you must do this in every new terminal)
source .venv/bin/activate
```

### Step 1.4: Install Python Dependencies

With the `venv` active, install all required Python packages from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

---

## 2. Hardware Configuration (`config.py`)

All hardware-specific settings (GPIO pins, sensor IDs, etc.) are stored in `config.py`. **You must edit this file to match your physical setup.**

*   `VALVE_PINS`, `PUMP_PINS`, `BOILER_PINS`: Set the BCM GPIO pin numbers for your relays/MOSFETs.
*   `LIGHT_PWM_PINS`, `FLOOR_HEATING_PINS`: Set the BCM GPIO pin numbers for PWM-controlled devices.
*   `ACTUATOR_PINS`: Set the pair of GPIO pins for the drawer lock actuator.
*   `SENSOR_IDS`: **Run the `testing/test_ds18b20_sensors.py` script to find the unique IDs** of your temperature sensors and update this dictionary.
*   `WATER_SENSOR_CONFIG`: Set the Trigger/Echo GPIO pins for your ultrasonic sensors. Measure your tanks and update the `dist_full` and `dist_empty` calibration values.
*   `BMS_MAC_ADDRESS`, `BMS_PROTOCOL`: **Use `bluetoothctl scan on` to find your BMS's MAC address** and update it here.
*   `HEATER_CONFIG`: **Use `ls -l /dev/serial/by-id/` to find your USB adapter's unique serial number** and update it here.

---

## 3. Running the System

### For Development (Manual Restart)

This is the best way to see live log output and test changes quickly.

1.  **Find and Stop the Old Process:**
    ```bash
    # Find the Process ID (PID)
    pgrep -f app.py
    
    # Stop the process (replace <PID> with the number you found)
    kill <PID>
    ```

2.  **Start the New Version Manually:**
    ```bash
    # Make sure you are in the project directory with the venv active
    cd ~/camper_backend
    source .venv/bin/activate
    
    # Run the app
    python app.py
    ```
    You will see all log output directly in your terminal. Press `Ctrl+C` to stop it.

### For Production (Automatic Startup)

The system is configured to start automatically on boot using the `start_camper_app.sh` script. To apply changes in production, simply edit your code and reboot the Pi.

```bash
sudo reboot
```
You can monitor the live logs with this command:
```bash
tail -f ~/camper_backend/debug.log
```

---

## 4. Individual Hardware Testing

A `testing/` directory is provided with simple, standalone scripts to test each piece of hardware individually before running the main application. This is essential for debugging wiring and configuration.

To use them, activate the virtual environment (`source .venv/bin/activate`) and run the desired script (e.g., `python testing/test_valves.py`).

---

## 5. File Structure

```
camper_backend/
│
├── hardware/
│   ├── __init__.py
│   ├── actuators.py
│   ├── autoterm_heater.py  (The 3rd party library)
│   ├── bms.py
│   ├── heater.py
│   ├── lights.py
│   ├── pumps.py
│   ├── pwm_devices.py
│   ├── sensors.py
│   ├── switches.py
│   ├── valves.py
│   └── water_level.py
│
├── testing/
│   ├── test_actuators.py
│   ├── test_bms.py
│   ├── test_ds18b20_sensors.py (Use this to find sensor IDs)
│   ├── test_heater.py
│   ├── test_lights_and_floors.py
│   ├── test_pumps_and_switches.py
│   ├── test_valves.py
│   └── test_water_sensors.py
│
├── app.py                  (The main server application)
├── config.py               (Your hardware configuration)
├── requirements.txt        (Python package list)
├── README.md               (This file)
├── boiler_temp_log.csv     (Auto-generated data log)
└── debug.log               (Auto-generated application log)
```