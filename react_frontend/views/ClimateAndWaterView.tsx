import React, { useState } from 'react';
import { VanState, SwitchDevice, DimmableDevice, DieselHeaterState, DieselHeaterMode } from '../types';
import FatSliderControl from '../components/FatSliderControl';
import SwitchButtonControl from '../components/SwitchButtonControl';
import { PowerIcon, HeaterIcon, TemperatureIcon, FlameIcon, FanIcon, BatteryIcon, WarningIcon } from '../components/Icons';

// --- This map remains the same ---
const statusTextMap: { [key in DieselHeaterState['status']]: string } = {
  off: 'Heater Off',
  starting: 'Starting...',
  warming_up: 'Warming Up',
  running: 'Running',
  shutting_down: 'Shutting Down',
};

// --- These sub-components remain the same ---
const DataPoint: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => (
    <div className="flex flex-col items-center justify-center text-center bg-stone-800/40 p-3 rounded-lg">
        <div className="text-amber-700">{icon}</div>
        <span className="text-sm font-medium text-stone-400 mt-1">{label}</span>
        <span className="text-lg font-bold text-stone-100">{value}</span>
    </div>
);

const ModeButton: React.FC<{ label: string; isActive: boolean; onClick: () => void; disabled?: boolean; }> = ({ label, isActive, onClick, disabled }) => {
    const baseClasses = "w-full text-center font-semibold py-2 px-4 rounded-lg transition-all duration-200 ease-in-out";
    const activeClasses = "bg-amber-700 text-white shadow-md";
    const inactiveClasses = "bg-stone-700/50 hover:bg-stone-600/60 text-stone-200";
    const disabledClasses = "opacity-50 cursor-not-allowed";

    return (
        <button onClick={onClick} disabled={disabled} className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses} ${disabled ? disabledClasses : ''}`}>
            {label}
        </button>
    );
};

// --- New Timer Toggle Button (for "Start In" / "Run For") ---
const TimerToggleButton: React.FC<{ label: string; isActive: boolean; onClick: () => void; disabled?: boolean; }> = ({ label, isActive, onClick, disabled }) => {
    const baseClasses = "flex-1 text-center font-semibold py-1.5 px-3 rounded-md transition-all duration-200 ease-in-out text-sm";
    const activeClasses = "bg-amber-700 text-white shadow-sm";
    const inactiveClasses = "bg-stone-700/50 hover:bg-stone-600/60 text-stone-200";
    const disabledClasses = "opacity-50 cursor-not-allowed";

    return (
        <button onClick={onClick} disabled={disabled} className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses} ${disabled ? disabledClasses : ''}`}>
            {label}
        </button>
    );
};


// --- Interface updated to include sensors ---
interface HeatingViewProps {
  sensors: VanState['sensors'];
  boiler: SwitchDevice;
  floorHeating: DimmableDevice;
  dieselHeater: DieselHeaterState;
  onUpdate: (updateFn: (prevState: VanState) => VanState) => void;
}

const HeatingView: React.FC<HeatingViewProps> = ({ sensors, boiler, floorHeating, dieselHeater, onUpdate }) => {
  
  // --- New state for the timer mode toggle ---
  // (Assumes 'timer' is a valid DieselHeaterMode in your types)
  const [timerType, setTimerType] = useState<'start_in' | 'run_for'>('run_for');

  // --- Simple handlers remain the same ---
  const handleBoilerToggle = (isOn: boolean) => {
    onUpdate(prevState => ({ ...prevState, boiler: { ...prevState.boiler, isOn } }));
  };

  const handleFloorHeatingChange = (level: number) => {
    onUpdate(prevState => ({ ...prevState, floorHeating: { ...prevState.floorHeating, level } }));
  };
  
  // --- New, more powerful heater handlers from your second file ---
  const handleHeaterUpdate = (update: Partial<DieselHeaterState>) => {
      onUpdate(prevState => ({
          ...prevState,
          dieselHeater: { ...prevState.dieselHeater, ...update }
      }));
  };

  const sendHeaterCommand = (command: object) => {
    // This special update function sends a command object to the backend
    onUpdate(prevState => ({ ...prevState, dieselHeater: { ...prevState.dieselHeater, ...command }}));
  };
  
  const handleStartHeater = () => {
    const { mode, powerLevel, setpoint, ventilationLevel, runTimer, startTimer } = dieselHeater;
    
    // Determine the value based on the mode
    let value: number;
    switch (mode) {
        case 'power':
            value = powerLevel;
            break;
        case 'temperature':
            value = setpoint;
            break;
        case 'ventilation':
            value = ventilationLevel;
            break;
        default:
             // Default to power mode if something is off, or handle 'timer' mode
             // If mode is 'timer', we don't send a value, just the timers.
             // The backend should know what to do if the mode is 'timer'.
             // Or, we assume the 'active' mode is still one of the others.
             // Let's assume the mode is whatever is *not* 'timer'.
             // This logic assumes 'mode' is one of temp/power/vent.
            value = setpoint; // Default to temperature
    }

    const startAction = {
        command: 'turn_on',
        mode: mode,
        value: value,
        run_timer_minutes: runTimer ? runTimer * 60 : null, // Convert hours to minutes
    };

    if (startTimer && startTimer > 0) {
        // If a start timer is set, wrap the action in a 'start_in' command
        sendHeaterCommand({
            command: 'start_in',
            value: startTimer * 60, // Convert hours to minutes
            action: startAction,
        });
        // Optimistically set status
        handleHeaterUpdate({ status: 'starting' }); // Or a new status like 'scheduled'
    } else {
        // Otherwise, send the start command directly
        sendHeaterCommand(startAction);
        // Optimistically update the UI to show 'starting' immediately
        handleHeaterUpdate({ status: 'starting' });
    }
  };
    
  const handleStopHeater = () => {
    if (dieselHeater.startTimer && dieselHeater.status === 'off') { // Check if a timer is set but heater is off
         // If a start timer is pending, cancel it
         sendHeaterCommand({ command: 'cancel_start_timer' });
         handleHeaterUpdate({ startTimer: null, status: 'off' }); // Clear timer and ensure status is off
    } else if (dieselHeater.status !== 'off' && dieselHeater.status !== 'shutting_down') {
         // If the heater is running, shut it down
         sendHeaterCommand({ command: 'shutdown' });
         handleHeaterUpdate({ status: 'shutting_down' }); // Optimistic UI update
    }
  };

  // --- Main Power Toggle Handler ---
  const handlePowerToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    const shouldBeOn = e.target.checked;
    if (shouldBeOn) {
        handleStartHeater();
    } else {
        handleStopHeater();
    }
  };

  // --- Derived state variables for UI logic ---
  const isTransitioning = dieselHeater.status === 'starting' || dieselHeater.status === 'shutting_down';
  const isStartTimerPending = (dieselHeater.startTimer || 0) > 0 && dieselHeater.status === 'off';
  const isHeaterOn = dieselHeater.status !== 'off';
  
  // Controls should be disabled if the heater is on OR a timer is pending
  const disableSettings = isHeaterOn || isStartTimerPending;

  const renderDieselHeaterControl = () => {
      switch (dieselHeater.mode) {
          case 'temperature':
              return (
                  <FatSliderControl
                      label="Set Temperature"
                      level={dieselHeater.setpoint}
                      onChange={level => handleHeaterUpdate({ setpoint: level })}
                      color="#b45309"
                      min={5} max={30} unit="°C"
                      disabled={disableSettings}
                  />
              );
          case 'power':
              return (
                  <FatSliderControl
                      label="Set Power Level"
                      level={dieselHeater.powerLevel}
                      onChange={level => handleHeaterUpdate({ powerLevel: level })}
                      color="#b45309"
                      min={1} max={9} unit=""
                      disabled={disableSettings}
                  />
              );
          case 'ventilation':
              return (
                  <FatSliderControl
                      label="Set Ventilation Speed"
                      level={dieselHeater.ventilationLevel}
                      onChange={level => handleHeaterUpdate({ ventilationLevel: level })}
                      color="#b45309"
                      min={1} max={9} unit=""
                      disabled={disableSettings}
                  />
              );
          // --- New 'timer' mode case ---
          case 'timer':
              const isStartIn = timerType === 'start_in';
              const level = isStartIn ? (dieselHeater.startTimer || 0) : (dieselHeater.runTimer || 0);
              
              return (
                  <div className="flex flex-col gap-3">
                      <div className="flex gap-2 p-1 bg-stone-900/30 rounded-lg">
                          <TimerToggleButton 
                              label="Run For" 
                              isActive={!isStartIn} 
                              onClick={() => setTimerType('run_for')}
                              disabled={disableSettings}
                          />
                          <TimerToggleButton 
                              label="Start In" 
                              isActive={isStartIn} 
                              onClick={() => setTimerType('start_in')}
                              disabled={disableSettings}
                          />
                      </div>
                      <FatSliderControl
                          label={isStartIn ? "Start In (Hours)" : "Run For (Hours)"}
                          level={level}
                          onChange={level => handleHeaterUpdate(
                              isStartIn ? { startTimer: level } : { runTimer: level }
                          )}
                          color={isStartIn ? "#4f46e5" : "#16a34a"} // indigo / green
                          min={0} max={12} unit="h"
                          disabled={disableSettings}
                      />
                  </div>
              );
          default:
              return null;
      }
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6 text-orange-200/65">Heating & Climate</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Basic Systems Card */}
        <div className="bg-orange-300/40 backdrop-blur-lg border border-white/10 rounded-2xl p-6 flex flex-col justify-center gap-8 shadow-xl shadow-orange-900/20 transition-all duration-300 ease-in-out hover:shadow-2xl hover:shadow-orange-900/40 hover:-translate-y-1.5">
            <SwitchButtonControl
                label={boiler.name}
                isOn={boiler.isOn}
                onToggle={() => handleBoilerToggle(!boiler.isOn)}
                icon={<HeaterIcon />}
                onColorClasses="bg-amber-700 text-white shadow-lg shadow-amber-700/50"
            />
            <FatSliderControl
                label={floorHeating.name}
                level={floorHeating.level}
                onChange={handleFloorHeatingChange}
                color="#b45309" // amber-700
            />
        </div>

        {/* Diesel Heater Card */}
        <div className="bg-orange-300/40 backdrop-blur-lg border border-white/10 rounded-2xl p-6 flex flex-col gap-4 shadow-xl shadow-orange-900/20 transition-all duration-300 ease-in-out hover:shadow-2xl hover:shadow-orange-900/40 hover:-translate-y-1.5">
            <div className="flex justify-between items-start">
                <div>
                    <h3 className="text-xl font-bold text-stone-100">Diesel Heater</h3>
                    <p className="text-amber-700 font-semibold">
                        {isStartTimerPending 
                            ? `Starts in ${dieselHeater.startTimer}h` 
                            : statusTextMap[dieselHeater.status]
                        }
                    </p>
                    {isHeaterOn && !isTransitioning && dieselHeater.timer && (
                        <p className="text-sm text-stone-300">Time remaining: {dieselHeater.timer}</p>
                    )}
                </div>
                <label htmlFor="diesel-heater-power" className="relative inline-flex items-center cursor-pointer">
                    <input 
                        type="checkbox" 
                        id="diesel-heater-power"
                        className="sr-only peer" 
                        checked={isHeaterOn || isStartTimerPending}
                        disabled={isTransitioning}
                        onChange={handlePowerToggle}
                    />
                    <div className="w-14 h-8 bg-stone-700 rounded-full peer peer-focus:ring-4 peer-focus:ring-amber-800 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-1 after:left-1 after:bg-white after:border-stone-600 after:border after:rounded-full after:h-6 after:w-6 after:transition-all after:duration-300 after:ease-in-out peer-checked:bg-amber-700 peer-checked:shadow-lg peer-checked:shadow-amber-800/40 transition-all duration-300 ease-in-out peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
                </label>
            </div>
            
            {dieselHeater.errors && dieselHeater.errors > 0 && (
                <div className="flex items-center p-3 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20">
                    <WarningIcon className="w-6 h-6 mr-3 flex-shrink-0" />
                    <span className="font-semibold">Heater Error Code: {dieselHeater.errors}</span>
                </div>
            )}
            
            <div className="grid grid-cols-3 gap-3">
                <DataPoint icon={<TemperatureIcon className="w-6 h-6"/>} label="Heater" value={`${dieselHeater.readings.heaterTemp}°C`} />
                <DataPoint icon={<FlameIcon className="w-6 h-6"/>} label="Flame" value={`${dieselHeater.readings.flameTemp}°C`} />
                {/* Updated to use sensor data like in your new file */}
                <DataPoint icon={<TemperatureIcon className="w-6 h-6"/>} label="Cabin" value={`${sensors.insideTemp.toFixed(1)}°C`} />
            </div>

            <div className="flex flex-col gap-4 mt-2">
                <div className="grid grid-cols-4 gap-3">
                    <ModeButton label="Temp" isActive={dieselHeater.mode === 'temperature'} onClick={() => handleHeaterUpdate({ mode: 'temperature' })} disabled={disableSettings} />
                    <ModeButton label="Power" isActive={dieselHeater.mode === 'power'} onClick={() => handleHeaterUpdate({ mode: 'power' })} disabled={disableSettings} />
                    <ModeButton label="Vent" isActive={dieselHeater.mode === 'ventilation'} onClick={() => handleHeaterUpdate({ mode: 'ventilation' })} disabled={disableSettings} />
                    {/* New Timer Mode Button */}
                    <ModeButton label="Timer" isActive={dieselHeater.mode === 'timer'} onClick={() => handleHeaterUpdate({ mode: 'timer' as DieselHeaterMode })} disabled={disableSettings} />
                </div>
                <div>
                    {renderDieselHeaterControl()}
                </div>
            </div>
        </div>

      </div>
    </div>
  );
};

export default HeatingView;