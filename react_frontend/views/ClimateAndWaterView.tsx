import React, { useState, useEffect } from 'react';
import { VanState, SwitchDevice, DimmableDevice, DieselHeaterState, DieselHeaterMode, DieselHeaterStatus } from '../types';
import FatSliderControl from '../components/FatSliderControl';
import SwitchButtonControl from '../components/SwitchButtonControl';
import { PowerIcon, HeaterIcon, TemperatureIcon, FlameIcon, FanIcon, BatteryIcon, WarningIcon } from '../components/Icons';



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


interface HeatingViewProps {
    boiler: SwitchDevice;
    floorHeating: DimmableDevice;
    dieselHeater: DieselHeaterState;
    onUpdate: (updateFn: (prevState: VanState) => VanState) => void;
}

const HeatingView: React.FC<HeatingViewProps> = ({ boiler, floorHeating, dieselHeater, onUpdate }) => {

    const handleBoilerToggle = (isOn: boolean) => {
        onUpdate(prevState => ({ ...prevState, boiler: { ...prevState.boiler, isOn } }));
    };

    const handleFloorHeatingChange = (level: number) => {
        onUpdate(prevState => ({ ...prevState, floorHeating: { ...prevState.floorHeating, level } }));
    };

    const handleDieselHeaterUpdate = (newHeaterState: Partial<DieselHeaterState>) => {
        onUpdate(prevState => ({
            ...prevState,
            dieselHeater: { ...prevState.dieselHeater, ...newHeaterState }
        }));
    };

    const [lastError, setLastError] = useState<string | null>(null);

    useEffect(() => {
        if (dieselHeater.errors && dieselHeater.errors !== 'No Error') {
            setLastError(dieselHeater.errors);
        }
    }, [dieselHeater.errors]);

    const handlePowerToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
        const shouldBeOn = e.target.checked;
        // If the user wants to turn it ON, it must be in 'Standby'
        if (shouldBeOn && dieselHeater.status === 'Standby') {
            setLastError(null); // Clear previous error when starting
            handleDieselHeaterUpdate({ status: 'starting' });
        }
        // If the user wants to turn it OFF, it must be in any state other than 'Standby'
        else if (!shouldBeOn && dieselHeater.status !== 'Standby') {
            handleDieselHeaterUpdate({ status: 'shutting_down' });
        }
    };

    const isHeaterOn = dieselHeater.status !== 'Standby';
    const isTransitioning = dieselHeater.status.includes('Starting') || dieselHeater.status.includes('Shutting');

    const renderDieselHeaterControl = () => {
        switch (dieselHeater.mode) {
            case 'temperature':
                return (
                    <FatSliderControl
                        label="Set Temperature"
                        level={dieselHeater.setpoint}
                        onChange={level => handleDieselHeaterUpdate({ setpoint: level })}
                        color="#b45309"
                        min={18}
                        max={30}
                        unit="°C"
                    />
                );
            case 'power':
                return (
                    <FatSliderControl
                        label="Set Power Level"
                        level={dieselHeater.powerLevel}
                        onChange={level => handleDieselHeaterUpdate({ powerLevel: level })}
                        color="#b45309"
                        min={0}
                        max={9}
                        unit=""
                    />
                );
            case 'ventilation':
                return (
                    <FatSliderControl
                        label="Set Ventilation Speed"
                        level={dieselHeater.ventilationLevel}
                        onChange={level => handleDieselHeaterUpdate({ ventilationLevel: level })}
                        color="#b45309"
                    />
                );
            default:
                return null;
        }
    };

    return (
        <div>
            <h1 className="text-3xl font-bold mb-6 text-orange-200/65">Heating</h1>
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
                            <p className="text-amber-700 font-semibold">{dieselHeater.status}</p>
                        </div>
                        <label htmlFor="diesel-heater-power" className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                id="diesel-heater-power"
                                className="sr-only peer"
                                checked={isHeaterOn}
                                disabled={isTransitioning}
                                onChange={handlePowerToggle}
                            />
                            <div className="w-14 h-8 bg-stone-700 rounded-full peer peer-focus:ring-4 peer-focus:ring-amber-800 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-1 after:left-1 after:bg-white after:border-stone-600 after:border after:rounded-full after:h-6 after:w-6 after:transition-all after:duration-300 after:ease-in-out peer-checked:bg-amber-700 peer-checked:shadow-lg peer-checked:shadow-amber-800/40 transition-all duration-300 ease-in-out peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
                        </label>
                    </div>

                    {(dieselHeater.errors && dieselHeater.errors !== 'No Error' || lastError) && (
                        <div className="flex items-center p-3 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20">
                            <WarningIcon className="w-6 h-6 mr-3 flex-shrink-0" />
                            <span className="font-semibold">Heater Error Code: {dieselHeater.errors && dieselHeater.errors !== 'No Error' ? dieselHeater.errors : lastError}</span>
                        </div>
                    )}

                    <div className="grid grid-cols-3 gap-3">
                        <DataPoint icon={<TemperatureIcon className="w-6 h-6" />} label="Heater" value={`${dieselHeater.readings.heaterTemp}°C`} />
                        <DataPoint icon={<FlameIcon className="w-6 h-6" />} label="Flame" value={`${dieselHeater.readings.flameTemp}°C`} />
                        <DataPoint icon={<TemperatureIcon className="w-6 h-6" />} label="Panel" value={`${dieselHeater.readings.panelTemp}°C`} />
                    </div>

                    <div className="flex flex-col gap-4 mt-2">
                        <div className="grid grid-cols-3 gap-3">
                            <ModeButton label="Temp" isActive={dieselHeater.mode === 'temperature'} onClick={() => handleDieselHeaterUpdate({ mode: 'temperature' })} />
                            <ModeButton label="Power" isActive={dieselHeater.mode === 'power'} onClick={() => handleDieselHeaterUpdate({ mode: 'power' })} />
                            <ModeButton label="Vent" isActive={dieselHeater.mode === 'ventilation'} onClick={() => handleDieselHeaterUpdate({ mode: 'ventilation' })} />
                        </div>
                        <div className={`transition-opacity duration-300 opacity-100`}>
                            {renderDieselHeaterControl()}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default HeatingView;