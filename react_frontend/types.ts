
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
export type DieselHeaterStatus = string;
export type DieselHeaterMode = 'temperature' | 'power' | 'ventilation' | 'timer';

export interface DieselHeaterState {
  status: DieselHeaterStatus;
  mode: DieselHeaterMode;
  setpoint: number; // Target temperature
  powerLevel: number; // Target power level %
  ventilationLevel: number; // Target ventilation level %

  // --- UPDATED FIELDS ---
  timer: number | null; // Remaining run time in minutes
  timerStartIn: number | null;     // REPLACES old 'timer'. In minutes, from backend.
  timerShutdownIn: number | null;  // NEW. In minutes, from backend.
  errors: string | null;

  readings: {
    heaterTemp: number;
    // externalTemp: number | null; // Can be null if not connected
    voltage: number;
    flameTemp: number;
    panelTemp: number;
  };

  // --- UI-ONLY STATE ---
  // These are for the sliders, in HOURS.
  startTimer?: number | null; // UI state: hours until start
  runTimer?: number | null;   // UI state: total run duration in hours

  // This is a temporary property used to send commands
  command?: string;
  value?: any;
  action?: any;
  run_timer_minutes?: number | null;
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