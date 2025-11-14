import React from 'react';
import { VanState, DimmableDevice, SwitchDevice } from '../types';
import FatSliderControl from '../components/FatSliderControl';
import SwitchButtonControl from '../components/SwitchButtonControl';
import { WaterDropIcon, VentIcon, HeaterIcon, LockIcon, UnlockIcon, PowerIcon } from '../components/Icons';

interface ControlsViewProps {
  lights: DimmableDevice[];
  switches: SwitchDevice[];
  onUpdate: (updateFn: (prevState: VanState) => VanState) => void;
}

const ControlsView: React.FC<ControlsViewProps> = ({ lights, switches, onUpdate }) => {

  const handleLightChange = (id: string, level: number) => {
    onUpdate(prevState => ({
      ...prevState,
      lights: prevState.lights.map(l => l.id === id ? { ...l, level } : l)
    }));
  };
  
  const handleSwitchToggle = (id:string, isOn: boolean) => {
    onUpdate(prevState => ({
      ...prevState,
      switches: prevState.switches.map(s => s.id === id ? { ...s, isOn } : s)
    }));
  };

  const getIconForSwitch = (id: string, isOn: boolean) => {
    // Per user request, all drains use a down-facing arrow icon.
    if (id.includes('drain')) {
      return <WaterDropIcon />;
    }
    if (id.includes('drawer')) return isOn ? <UnlockIcon /> : <LockIcon />;
    if (id.includes('hot')) return <HeaterIcon />;
    if (id.includes('pump')) return <PowerIcon />;
    // Fallback icon
    return <PowerIcon />;
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6 text-orange-200/65">Controls</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Column: Lights */}
        <div className="md:col-span-1 bg-orange-300/40 backdrop-blur-lg border border-white/10 rounded-2xl p-4 flex flex-col justify-between shadow-xl shadow-orange-900/20 transition-all duration-300 ease-in-out hover:shadow-2xl hover:shadow-orange-900/40 hover:-translate-y-1.5">
          {lights.map(light => (
            <FatSliderControl
              key={light.id}
              label={light.name}
              level={light.level}
              onChange={(level) => handleLightChange(light.id, level)}
              color="#b45309" // amber-700
            />
          ))}
        </div>

        {/* Right Column: Switches */}
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          {switches.map(s => (
            <SwitchButtonControl
              key={s.id}
              label={s.name}
              isOn={s.isOn}
              onToggle={() => handleSwitchToggle(s.id, !s.isOn)}
              icon={getIconForSwitch(s.id, s.isOn)}
            />
          ))}
        </div>

      </div>
    </div>
  );
};

export default ControlsView;