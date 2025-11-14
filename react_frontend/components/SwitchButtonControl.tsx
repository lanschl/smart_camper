import React from 'react';

interface SwitchButtonControlProps {
  label: string;
  isOn: boolean;
  onToggle: () => void;
  icon: React.ReactElement<{ className?: string }>;
  onColorClasses?: string;
}

const SwitchButtonControl: React.FC<SwitchButtonControlProps> = ({ label, isOn, onToggle, icon, onColorClasses }) => {
  const baseClasses = "w-full h-28 rounded-2xl flex flex-col items-center justify-center p-2 font-semibold transition-all duration-300 ease-in-out transform active:scale-95 hover:-translate-y-1";
  const defaultOnClasses = "bg-amber-700 text-white shadow-xl shadow-amber-800/40 hover:shadow-2xl hover:shadow-amber-800/60";
  const onClasses = onColorClasses || defaultOnClasses;
  const offClasses = "bg-stone-800/40 text-stone-200 hover:bg-stone-700/50 backdrop-blur-md border border-white/10 shadow-xl shadow-stone-950/20 hover:shadow-2xl hover:shadow-stone-950/30";

  return (
    <button
      onClick={onToggle}
      className={`${baseClasses} ${isOn ? onClasses : offClasses}`}
    >
      {React.cloneElement(icon, { className: 'w-8 h-8 mb-2' })}
      <span className="text-center text-base leading-tight">{label}</span>
    </button>
  );
};

export default SwitchButtonControl;