import React, { useState, useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { VanState, View, DieselHeaterState } from './types'; // Import DieselHeaterState
// import BottomNav from './components/BottomNav';
//import SideNav from './components/SideNav';
import TopNav from './components/TopNav';
import DashboardView from './views/DashboardView';
import ControlsView from './views/ControlsView';
import ClimateAndWaterView from './views/ClimateAndWaterView';

const SOCKET_SERVER_URL = 'http://localhost:5000';

const initialVanState: VanState = {
  sensors: {
    freshWater: 0,
    grayWater: 0,
    boilerTemp: 0,
    insideTemp: 0,
    outsideTemp: 0,
    batterySoC: 0, // Should come from BMS
    batteryVoltage: 0,
    batteryAmperage: 0,
    batteryPower: 0,
    boilerTempHistory: [],
  },
  lights: [
    { id: 'deko', name: 'Deko Lights', level: 0 },
    { id: 'ambiente', name: 'Ambiente Lights', level: 0 },
    { id: 'ceiling', name: 'Ceiling Lights', level: 0 },
  ],
  switches: [
    { id: 'gray_drain', name: 'Gray Water Drain', isOn: false },
    { id: 'fresh_winter_drain', name: 'Fresh Winter Drain', isOn: false },
    { id: 'shower_drain', name: 'Shower Drain Pump', isOn: false },
    { id: 'fresh_pump', name: 'Fresh Water Pump', isOn: false },
    { id: 'hot_pump', name: 'Hot Water Pump', isOn: false },
    { id: 'drawers', name: 'Drawer Locks', isOn: false },
  ],
  boiler: { id: 'boiler_heat', name: 'Boiler Heating Coil', isOn: false },
  floorHeating: { id: 'floor_heat', name: 'Heated Floors', level: 0 },
  dieselHeater: {
    status: 'Standby',
    mode: 'power',
    setpoint: 24,
    powerLevel: 5,
    ventilationLevel: 0,

    timerStartIn: null,
    timerShutdownIn: null,

    readings: { heaterTemp: 0, voltage: 0, flameTemp: 0, panelTemp: 0 },
    errors: null,
  }
};

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<View>('dashboard');
  const [vanState, setVanState] = useState<VanState>(initialVanState);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = io(SOCKET_SERVER_URL);
    socketRef.current = socket;
    socket.on('connect', () => console.log('Connected to Python backend!'));
    socket.on('disconnect', () => console.log('Disconnected from Python backend.'));

    // --- MODIFIED SENSOR UPDATE LISTENER ---
    socket.on('sensor_update', (sensorData: Partial<VanState['sensors'] & { dieselHeater: DieselHeaterState }>) => {
      setVanState(prevState => {
        const newState = { ...prevState };
        const { dieselHeater, ...otherSensors } = sensorData;

        // Merge the main sensor data (temp, water, bms)
        newState.sensors = { ...newState.sensors, ...otherSensors };

        // If the update contains dieselHeater data, merge it separately
        if (dieselHeater) {
          newState.dieselHeater = { ...prevState.dieselHeater, ...dieselHeater }; // <-- FIX
        }
        return newState;
      });
    });

    return () => { socket.disconnect(); };
  }, []);

  // The simulation useEffect is now correctly REMOVED.

  const handleUpdate = (updateFn: (prevState: VanState) => VanState) => {
    const socket = socketRef.current;
    if (!socket) {
      console.error("Socket not connected!");
      setVanState(updateFn);
      return;
    }

    const prevState = vanState; // Get state *before* update for comparison
    const newState = updateFn(prevState);

    // --- MERGED LOGIC ---

    // 1. Diesel Heater Commands (NEW)
    const prevHeater = prevState.dieselHeater;
    const newHeater = newState.dieselHeater;

    if (prevHeater.status === 'Standby' && newHeater.status === 'starting') {
      let value = newHeater.mode === 'power' ? newHeater.powerLevel : newHeater.setpoint;
      if (newHeater.mode === 'ventilation') {
        socket.emit('diesel_heater_command', { command: 'turn_on_ventilation', value: newHeater.ventilationLevel });
      } else {
        socket.emit('diesel_heater_command', { command: 'turn_on', mode: newHeater.mode, value });
      }
    } else if (prevHeater.status !== 'Standby' && newHeater.status === 'shutting_down') {
      socket.emit('diesel_heater_command', { command: 'shutdown' });
    } else if (!newHeater.status.includes('Starting') && !newHeater.status.includes('Shutting') && !newHeater.status.includes('Cooling') && newHeater.status !== 'Standby') {
      if (prevHeater.mode !== newHeater.mode ||
        (newHeater.mode === 'temperature' && prevHeater.setpoint !== newHeater.setpoint) ||
        (newHeater.mode === 'power' && prevHeater.powerLevel !== newHeater.powerLevel)) {

        let value = newHeater.mode === 'power' ? newHeater.powerLevel : newHeater.setpoint;
        socket.emit('diesel_heater_command', { command: 'change_setting', mode: newHeater.mode, value: value });
      }
    }

    // 2. Main Switches Array (KEPT FROM YOUR VERSION)
    newState.switches.forEach((newSwitch, index) => {
      const oldSwitch = prevState.switches[index];
      if (oldSwitch && oldSwitch.isOn !== newSwitch.isOn) {
        socket.emit('switch_toggle', { id: newSwitch.id, isOn: newSwitch.isOn });
      }
    });

    // 3. Dimmable Lights (KEPT FROM YOUR VERSION)
    newState.lights.forEach((newLight, index) => {
      const oldLight = prevState.lights[index];
      if (oldLight && oldLight.level !== newLight.level) {
        socket.emit('light_change', { id: newLight.id, level: newLight.level });
      }
    });

    // 4. Standalone Boiler Switch (KEPT FROM YOUR VERSION)
    if (prevState.boiler.isOn !== newState.boiler.isOn) {
      socket.emit('switch_toggle', { id: newState.boiler.id, isOn: newState.boiler.isOn });
    }

    // 5. Standalone Floor Heating (KEPT FROM YOUR VERSION)
    if (prevState.floorHeating.level !== newState.floorHeating.level) {
      socket.emit('floor_heating_change', { id: newState.floorHeating.id, level: newState.floorHeating.level });
    }

    // Finally, update the UI with the new state
    setVanState(newState);
  };

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardView sensors={vanState.sensors} />;
      case 'controls':
        return <ControlsView lights={vanState.lights} switches={vanState.switches} onUpdate={handleUpdate} />;
      case 'heating':
        // Pass the live sensor data to the heating view as well
        return <ClimateAndWaterView sensors={vanState.sensors} boiler={vanState.boiler} floorHeating={vanState.floorHeating} onUpdate={handleUpdate} dieselHeater={vanState.dieselHeater} />;
      default:
        return <DashboardView sensors={vanState.sensors} />;
    }
  };

  return (
    <div className="font-sans text-stone-800 min-h-screen"> {/* Removed flex layout */}

      {/* The new TopNav is now a self-managing overlay component */}
      <TopNav activeView={activeView} setActiveView={setActiveView} />

      {/* The main content area now has padding at the top to make space for the nav bar */}
      <main className="p-4 md:p-6 pt-28"> {/* Added pt-28 (padding-top) */}
        {renderView()}
      </main>

    </div>
  );
};

export default App;