# hardware/sensors.py
from w1thermsensor import W1ThermSensor
from typing import Dict, Optional

class SensorReader:
    """
    Reads temperature data from DS18B20 sensors using their unique IDs.
    """
    def __init__(self, sensor_id_config: Dict[str, str]):
        print("Initializing Sensor Reader...")
        self.sensor_id_config = sensor_id_config
        self.sensors: Dict[str, Optional[W1ThermSensor]] = {}
        self.is_mocked = False

        try:
            available_sensors = {s.id: s for s in W1ThermSensor.get_available_sensors()}
            if not available_sensors:
                raise RuntimeError("No 1-Wire sensors found.")
                
            for name, sensor_id in self.sensor_id_config.items():
                if sensor_id in available_sensors:
                    self.sensors[name] = available_sensors[sensor_id]
                    print(f"  - Found and linked sensor '{name}' (ID: {sensor_id})")
                else:
                    self.sensors[name] = None
                    print(f"  - WARNING: Sensor for '{name}' (ID: {sensor_id}) not found!")
            print("Sensor Reader initialized successfully.")

        except Exception as e:
            print(f"Error initializing w1thermsensor: {e}")
            print("Sensor reading will be mocked.")
            self.is_mocked = True

    def read_all_sensors(self) -> Dict[str, Optional[float]]:
        """
        Reads all configured sensors and returns a dictionary of their temperatures.
        Returns temperature in Celsius.
        """
        readings = {}
        if self.is_mocked:
            # Return some fake data if initialization failed
            return {'insideTemp': 21.5, 'outsideTemp': 9.8, 'boilerTemp': 62.1}

        for name, sensor in self.sensors.items():
            if sensor:
                try:
                    # Get temperature and round to one decimal place
                    temp = round(sensor.get_temperature(), 1)
                    readings[name] = temp
                except Exception as e:
                    print(f"Could not read sensor '{name}': {e}")
                    readings[name] = None # Return None on error
            else:
                readings[name] = None
        
        return readings