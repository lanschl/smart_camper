import React, { useState, useEffect, useRef } from 'react';
import { View } from '../types';
import { DashboardIcon, LightbulbIcon, HeaterIcon } from './Icons';

interface TopNavProps {
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
      className={`flex flex-col items-center justify-center w-24 h-24 rounded-2xl transition-all duration-300 ease-in-out transform active:scale-95 hover:-translate-y-1
        ${isActive
          ? 'bg-orange-200/65 text-white'
          : 'text-orange-200 hover:bg-stone-700/50'
        }`}
    >
      {children}
      <span className="text-xs font-medium mt-1">{label}</span>
    </button>
  );
};

const TopNav: React.FC<TopNavProps> = ({ activeView, setActiveView }) => {
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<number | null>(null);

  // Auto-closing timer logic
  useEffect(() => {
    if (isOpen) {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        setIsOpen(false);
      }, 3000); // Close after 3 seconds of inactivity
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isOpen, activeView]); // Reset timer if isOpen or the activeView changes

  const handleNavButtonClick = (view: View) => {
    setActiveView(view);
    setIsOpen(false); // Close immediately after selection
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  const handleToggle = () => {
    setIsOpen(prev => !prev);
  };

  return (
    <>
      {/* --- The Drop-Down Panel --- */}
      <header
        className={`fixed top-0 left-1/2 -translate-x-1/2 z-20 flex items-center justify-center p-2 rounded-b-2xl bg-stone-800/30 backdrop-blur-lg border-x border-b border-stone-700/50 shadow-xl shadow-black/30 transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-y-0' : '-translate-y-full'}`}
      >
        <nav className="flex items-center justify-center gap-2">
          <NavButton label="Dashboard" view="dashboard" activeView={activeView} onClick={handleNavButtonClick}>
            <DashboardIcon className="w-8 h-8" />
          </NavButton>
          <NavButton label="Controls" view="controls" activeView={activeView} onClick={handleNavButtonClick}>
            <LightbulbIcon className="w-8 h-8" />
          </NavButton>
          <NavButton label="Heating" view="heating" activeView={activeView} onClick={handleNavButtonClick}>
            <HeaterIcon className="w-8 h-8" />
          </NavButton>
          <NavButton label="Weekly" view="weekly" activeView={activeView} onClick={handleNavButtonClick}>
            <span className="text-2xl font-bold">📅</span>
          </NavButton>
        </nav>
      </header>

      {/* --- The "Peek-a-boo" Handle --- */}
      <button
        onClick={handleToggle}
        className="fixed top-0 left-1/2 -translate-x-1/2 z-30 w-24 h-6 bg-stone-800/50 backdrop-blur-md rounded-b-lg border-x border-b border-stone-700/50 flex items-center justify-center text-orange-200/50 hover:bg-stone-700/50 transition-all duration-300"
        aria-label="Toggle navigation"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`h-5 w-5 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
    </>
  );
};

export default TopNav;