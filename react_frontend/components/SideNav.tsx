import React, { useState, useEffect, useRef } from 'react';
import { View } from '../types';
import { DashboardIcon, LightbulbIcon, HeaterIcon } from './Icons';

interface SideNavProps {
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

const SideNav: React.FC<SideNavProps> = ({ activeView, setActiveView }) => {
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<number | null>(null);

  // This effect handles the auto-closing timer
  useEffect(() => {
    // If the nav is opened, set a timer to close it.
    if (isOpen) {
      // Clear any existing timer first
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = window.setTimeout(() => {
        setIsOpen(false);
      }, 3000); // Close after 3 seconds
    }
    
    // Cleanup function to clear the timer if the component is unmounted
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [isOpen]); // This effect re-runs whenever 'isOpen' changes

  const handleNavButtonClick = (view: View) => {
    setActiveView(view);
    setIsOpen(false); // Close the nav immediately after a selection
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  };

  const handleToggle = () => {
    setIsOpen(prev => !prev);
  }

  return (
    <>
      {/* --- The Fly-out Panel --- */}
      {/* This is the main menu that slides in and out */}
      <aside 
        className={`fixed top-0 left-0 h-full z-20 flex flex-col items-center justify-center gap-4 bg-stone-800/80 backdrop-blur-lg border-r border-stone-700/50 transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
        style={{ width: '10rem' }} // A slightly wider 160px
      >
        <NavButton label="Dashboard" view="dashboard" activeView={activeView} onClick={handleNavButtonClick}>
            <DashboardIcon className="w-10 h-10" />
        </NavButton>
        <NavButton label="Controls" view="controls" activeView={activeView} onClick={handleNavButtonClick}>
            <LightbulbIcon className="w-10 h-10" />
        </NavButton>
        <NavButton label="Heating" view="heating" activeView={activeView} onClick={handleNavButtonClick}>
            <HeaterIcon className="w-10 h-10" />
        </NavButton>
      </aside>

      {/* --- The "Peek-a-boo" Handle --- */}
      {/* This small button is always visible on the edge */}
      <button
        onClick={handleToggle}
        className="fixed top-1/2 -translate-y-1/2 left-0 z-30 w-6 h-24 bg-stone-800/50 backdrop-blur-md rounded-r-lg border-y border-r border-stone-700/50 flex items-center justify-center text-orange-200/50 hover:bg-stone-700/50 transition-all duration-300"
        aria-label="Toggle navigation"
      >
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          className={`h-6 w-6 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </>
  );
};

export default SideNav;