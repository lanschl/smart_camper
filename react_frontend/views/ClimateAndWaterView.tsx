import React, { useState } from 'react';
import { VanState, SwitchDevice, DimmableDevice, DieselHeaterState, DieselHeaterMode } from '../types';
import FatSliderControl from '../components/FatSliderControl';
import SwitchButtonControl from '../components/SwitchButtonControl';
import { PowerIcon, HeaterIcon, TemperatureIcon, FlameIcon, FanIcon, BatteryIcon, WarningIcon } from '../components/Icons';

// --- REMOVED statusTextMap ---
// The backend now sends the raw status string.

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
  const [timerType, setTimerType] = useState<'start_in' | 'run_for'>('run_for');

  // --- *** NEW: State to remember which mode to start in (Fixes 'timer' mode bug) *** ---
  // This remembers the *actual* mode (Temp/Power/Vent) even when you're on the "Timer" tab
  const [startMode, setStartMode] = useState<DieselHeaterMode>('temperature');

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
  
  // --- *** UPDATED: handleStartHeater *** ---
  const handleStartHeater = () => {
    // Get UI slider values (in hours)
    const { powerLevel, setpoint, ventilationLevel, runTimer, startTimer } = dieselHeater;
    
    // Determine the value and mode-to-send based on the *remembered* startMode
    let value: number;
    let modeToSend: DieselHeaterMode;

    switch (startMode) { // Use startMode, NOT dieselHeater.mode
        case 'power':
            value = powerLevel;
            modeToSend = 'power';
            break;
        case 'ventilation':
            value = ventilationLevel;
            modeToSend = 'ventilation';
            break;
        case 'temperature':
        default:
            value = setpoint;
            modeToSend = 'temperature';
            break;
    }

    // Build the action that the backend will run
    const startAction = {
        command: modeToSend === 'ventilation' ? 'turn_on_ventilation' : 'turn_on',
        mode: modeToSend,
        value: value,
        run_timer_minutes: runTimer && runTimer > 0 ? runTimer * 60 : null, // Convert hours to minutes
    };

    if (startTimer && startTimer > 0) {
        // If a start timer is set, wrap the action in a 'start_in' command
        sendHeaterCommand({
            command: 'start_in',
            value: startTimer * 60, // Convert hours to minutes
            action: startAction,
        });
    } else {
        // Otherwise, send the start command directly
        sendHeaterCommand(startAction);
    }
    // Optimistic UI update (backend will confirm)
    handleHeaterUpdate({ status: 'Starting...' });
  };
    
  // --- *** UPDATED: handleStopHeater *** ---
  const handleStopHeater = () => {
    // Get backend timer/status state
    const { timerStartIn, status } = dieselHeater;

    // Check if a 'start_in' timer is pending
    if (timerStartIn && timerStartIn > 0) {
         // If a start timer is pending, cancel it
         sendHeaterCommand({ command: 'cancel_start_timer' });
         handleHeaterUpdate({ timerStartIn: null, status: 'Standby' }); // Optimistic UI update
    } else {
         // If the heater is on or starting, shut it down
         // Check if status is NOT one of the "off" states
         const isOff = status === 'Standby' || status.includes('Shutting Down') || status.includes('Cooling Down');
         if (!isOff) {
            sendHeaterCommand({ command: 'shutdown' });
            handleHeaterUpdate({ status: 'Shutting Down', timerShutdownIn: null }); // Optimistic UI update
         }
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

  // --- *** UPDATED: Derived state variables for UI logic *** ---
  const { status, timerStartIn, timerShutdownIn } = dieselHeater;

  // A timer is pending if the backend says timerStartIn > 0
  const isStartTimerPending = (timerStartIn || 0) > 0;

  // The heater is "on" if it's not in an "off" state and not just pending
  const isOff = status === 'Standby' || status.includes('Shutting Down') || status.includes('Cooling Down');
  const isHeaterOn = !isOff && !isStartTimerPending;

  // It's "transitioning" if it's starting or stopping
  const isTransitioning = status.includes('Starting') || status.includes('Shutting Down') || status.includes('Cooling Down');
  
  // Controls should be disabled if the heater is on OR a timer is pending
  const disableSettings = isHeaterOn || isStartTimerPending;

  const renderDieselHeaterControl = () => {
      // This logic remains the same, as it's for the UI state
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
          // --- Timer mode case ---
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
                          step={0.5} // Allow 30-min increments
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
        
        {/* Basic Systems Card (Unchanged) */}
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
                    {/* --- *** UPDATED: Status and Timer Display *** --- */}
                    <p className="text-amber-700 font-semibold h-6">
                        {isStartTimerPending 
                            ? `Starts in ${timerStartIn} min` 
                            : (dieselHeater.status || 'Standby') // Display raw status
                        }
                    </p>
                    {isHeaterOn && !isTransitioning && timerShutdownIn && timerShutdownIn > 0 && (
                        <p className="text-sm text-stone-300">
                          Time remaining: {timerShutdownIn} min
                        </p>
                    )}
                </div>
                <label htmlFor="diesel-heater-power" className="relative inline-flex items-center cursor-pointer">
                    <input 
                        type="checkbox" 
                        id="diesel-heater-power"
                        className="sr-only peer" 
                        checked={isHeaterOn || isStartTimerPending} // Use new derived state
                        disabled={isTransitioning} // Use new derived state
                        onChange={handlePowerToggle}
                    />
                    <div className="w-14 h-8 bg-stone-700 rounded-full peer peer-focus:ring-4 peer-focus:ring-amber-800 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-1 after:left-1 after:bg-white after:border-stone-600 after:border after:rounded-full after:h-6 after:w-6 after:transition-all after:duration-300 after:ease-in-out peer-checked:bg-amber-700 peer-checked:shadow-lg peer-checked:shadow-amber-800/40 transition-all duration-300 ease-in-out peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
                </label>
            </div>
            
            {/* --- *** UPDATED: Error Display *** --- */}
            {dieselHeater.errors && dieselHeater.errors !== 'No Error' && (
                <div className="flex items-center p-3 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20">
                    <WarningIcon className="w-6 h-6 mr-3 flex-shrink-0" />
                    <span className="font-semibold">Heater Error: {dieselHeater.errors}</span>
                </div>
            )}
            
            {/* DataPoint display remains the same, but will get new data */}
            <div className="grid grid-cols-3 gap-3">
                <DataPoint icon={<TemperatureIcon className="w-6 h-6"/>} label="Heater" value={`${dieselHeater.readings.heaterTemp}°C`} />
                <DataPoint icon={<FlameIcon className="w-6 h-6"/>} label="Flame" value={`${dieselHeater.readings.flameTemp}°C`} />
                <DataPoint icon={<TemperatureIcon className="w-6 h-6"/>} label="Cabin" value={`${sensors.insideTemp.toFixed(1)}°C`} />
            </div>

            <div className="flex flex-col gap-4 mt-2">
                <div className="grid grid-cols-4 gap-3">
                    {/* --- *** UPDATED: Mode Buttons set startMode *** --- */}
                    <ModeButton label="Temp" isActive={dieselHeater.mode === 'temperature'} onClick={() => { handleHeaterUpdate({ mode: 'temperature' }); setStartMode('temperature'); }} disabled={disableSettings} />
                    <ModeButton label="Power" isActive={dieselHeater.mode === 'power'} onClick={() => { handleHeaterUpdate({ mode: 'power' }); setStartMode('power'); }} disabled={disableSettings} />
                    <ModeButton label="Vent" isActive={dieselHeater.mode === 'ventilation'} onClick={() => { handleHeaterUpdate({ mode: 'ventilation' }); setStartMode('ventilation'); }} disabled={disableSettings} />
                    <ModeButton label="Timer" isActive={dieselHeater.mode === 'timer'} onClick={() => handleHeaterUpdate({ mode: 'timer' })} disabled={disableSettings} />
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