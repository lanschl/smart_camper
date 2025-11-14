
export type View = 'dashboard' | 'controls' | 'heating';

export interface DimmableDevice {
  id: string;
  name: string;
  level: number; // 0-100
}

export interface SwitchDevice {
  id: string;
  name: string;
  isOn: boolean;
}

// New detailed types for the Diesel Heater
export type DieselHeaterStatus = 'off' | 'starting' | 'warming_up' | 'running' | 'shutting_down';
export type DieselHeaterMode = 'temperature' | 'power' | 'ventilation';

export interface DieselHeaterState {
  status: DieselHeaterStatus;
  mode: DieselHeaterMode;
  setpoint: number; // Target temperature
  powerLevel: number; // Target power level %
  ventilationLevel: number; // Target ventilation level %
  timer: number | null; // minutes remaining
  readings: {
    heaterTemp: number;
    externalTemp: number;
    voltage: number;
    flameTemp: number;
    panelTemp: number;
  };
  errors: number | null; // Error code
}


export interface VanState {
  sensors: {
    freshWater: number; // 0-100
    grayWater: number; // 0-100
    boilerTemp: number; // Celsius
    insideTemp: number; // Celsius
    outsideTemp: number; // Celsius
    batterySoC: number; // 0-100
    batteryVoltage: number; // Volts
    batteryAmperage: number; // Amps, positive for charging
    batteryPower: number; // Power in W
    boilerTempHistory: { time: number; temp: number }[]; // time as timestamp
  };
  lights: DimmableDevice[];
  switches: SwitchDevice[];
  boiler: SwitchDevice;
  floorHeating: DimmableDevice;
  dieselHeater: DieselHeaterState;
}