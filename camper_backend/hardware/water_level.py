# hardware/water_level.py

from gpiozero import DistanceSensor
from gpiozero.exc import GPIOZeroError
from typing import Dict, List
import statistics
import logging

class WaterLevelController:
    """
    Manages JSN-SR04T sensors to calculate tank fill percentages.
    This version creates and destroys sensor objects on-demand to prevent
    continuous background polling.
    """
    def __init__(self, config: Dict):
        # We no longer initialize devices here. We just store the configuration.
        logging.info("Initializing Water Level Controller (On-Demand Mode)...")
        self.config = config
        self.is_mocked = False
        # A quick check to see if gpiozero is likely to work
        try:
            from gpiozero import Device
            Device.ensure_pin_factory()
        except GPIOZeroError as e:
            logging.error(f"Error initializing gpiozero pin factory: {e}")
            self.is_mocked = True

    def _get_single_reading(self, trigger_pin: int, echo_pin: int) -> float:
        """
        Creates a sensor, takes one reading, and closes it.
        Returns distance in cm.
        """
        sensor = None
        try:
            sensor = DistanceSensor(echo=echo_pin, trigger=trigger_pin)
            # The distance property will wait for a single valid reading
            distance_cm = sensor.distance * 100
            return distance_cm
        except GPIOZeroError as e:
            logging.warning(f"Could not read sensor on T{trigger_pin}/E{echo_pin}: {e}")
            return 0.0
        finally:
            # This is crucial: always close the sensor to stop background threads
            # and release GPIO pins.
            if sensor:
                sensor.close()

    def _distance_to_percent(self, distance_cm: float, dist_full: float, dist_empty: float) -> int:
        # ... (This function remains exactly the same) ...
        if distance_cm is None:
            return 0
        total_range = dist_empty - dist_full
        if total_range <= 0:
            return 0
        water_height = dist_empty - distance_cm
        percentage = (water_height / total_range) * 100
        return int(max(0, min(100, percentage)))

    def read_levels(self) -> Dict[str, int]:
        """Reads all sensors and returns a dictionary of tank percentages."""
        if self.is_mocked:
            return {'freshWater': 78, 'grayWater': 45}

        # --- Freshwater Logic ---
        fresh_config = self.config['freshWater']
        fresh_distances: List[float] = []
        if fresh_config['sensors']:
            for sensor_name, pins in fresh_config['sensors'].items():
                logging.info(f"Reading sensor '{sensor_name}'...")
                dist = self._get_single_reading(pins['trigger_pin'], pins['echo_pin'])
                if dist > 0:
                    fresh_distances.append(dist)
        
        fresh_percent = 0
        if fresh_distances:
            avg_distance = statistics.mean(fresh_distances)
            fresh_percent = self._distance_to_percent(
                avg_distance, fresh_config['dist_full'], fresh_config['dist_empty']
            )

        # --- Gray Water Logic ---
        gray_config = self.config['grayWater']
        gray_percent = 0
        if gray_config['sensors']:
            gray_sensor_name = list(gray_config['sensors'].keys())[0]
            pins = gray_config['sensors'][gray_sensor_name]
            logging.info(f"Reading sensor '{gray_sensor_name}'...")
            gray_distance = self._get_single_reading(pins['trigger_pin'], pins['echo_pin'])

            if gray_distance > gray_config['full_override_threshold']:
                gray_percent = 95
            elif gray_distance > 0:
                gray_percent = self._distance_to_percent(
                    gray_distance, gray_config['dist_full'], gray_config['dist_empty']
                )

        return {
            'freshWater': fresh_percent,
            'grayWater': gray_percent
        }

    def cleanup(self):
        # We no longer hold devices open, so cleanup is not strictly necessary,
        # but it's good practice to have the method for consistency.
        logging.info("Water level controller cleanup (no devices to close).")