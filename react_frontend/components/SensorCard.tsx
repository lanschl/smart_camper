import React from 'react';

interface SensorCardProps {
    icon: React.ReactNode;
    title: string;
    value: React.ReactNode; // Changed to allow styled components
    children?: React.ReactNode;
    className?: string; // Added to allow conditional styling
    style?: React.CSSProperties;
}

const SensorCard: React.FC<SensorCardProps> = ({ icon, title, value, children, className, style }) => {
    return (
        <div 
            className={`bg-orange-300/40 backdrop-blur-lg border border-white/10 rounded-2xl shadow-xl shadow-orange-900/20 p-3 flex flex-col h-full transition-all duration-300 ease-in-out hover:shadow-2xl hover:shadow-orange-900/40 hover:-translate-y-1.5 ${className || ''}`}
            style={style}
        >
            <div>
                <div className="flex items-center text-orange-100">
                    {icon}
                    <span className="ml-2 font-medium">{title}</span>
                </div>
                <div className="text-4xl font-bold text-stone-100 mt-2 transition-colors duration-300">
                    {value}
                </div>
            </div>
            {children && <div className="mt-2 flex-grow flex flex-col items-center justify-center">{children}</div>}
        </div>
    );
};

export default SensorCard;