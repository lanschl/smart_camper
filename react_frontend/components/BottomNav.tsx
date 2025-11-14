import React from 'react';
import { View } from '../types';
import { DashboardIcon, LightbulbIcon, HeaterIcon } from './Icons';

interface BottomNavProps {
  activeView: View;
  setActiveView: (view: View) => void;
}

const NavButton: React.FC<{
    label: string;
    view: View;
    activeView: View;
    onClick: (view: View) => void;
    children: React.ReactNode;
}> = ({ label, view, activeView, onClick, children }) => {
  const isActive = activeView === view;
  return (
    <button
      onClick={() => onClick(view)}
      className={`flex flex-col items-center justify-center w-24 h-14 rounded-2xl transition-all duration-300 ease-in-out transform active:scale-95 hover:-translate-y-1
        ${isActive 
          ? 'bg-orange-200/65 text-white' 
          : 'text-orange-200 hover:bg-stone-500/10'
        }`}
    >
      {children}
      <span className="text-xs font-medium mt-1">{label}</span>
    </button>
  );
};

const BottomNav: React.FC<BottomNavProps> = ({ activeView, setActiveView }) => {
  return (
    <footer className="fixed bottom-4 left-1/2 -translate-x-1/2 w-auto">
      <nav className="flex items-center justify-center gap-2 p-2 rounded-full bg-stone-800/50 backdrop-blur-lg border border-stone-700/50 shadow-xl shadow-black/30">
        <NavButton label="Dashboard" view="dashboard" activeView={activeView} onClick={setActiveView}>
            <DashboardIcon className="w-6 h-6" />
        </NavButton>
        <NavButton label="Controls" view="controls" activeView={activeView} onClick={setActiveView}>
            <LightbulbIcon className="w-6 h-6" />
        </NavButton>
        <NavButton label="Heating" view="heating" activeView={activeView} onClick={setActiveView}>
            <HeaterIcon className="w-6 h-6" />
        </NavButton>
      </nav>
    </footer>
  );
};

export default BottomNav;