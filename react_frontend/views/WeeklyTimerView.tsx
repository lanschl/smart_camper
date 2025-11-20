import React, { useState, useEffect } from 'react';

const WeeklyTimerView: React.FC = () => {
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const currentDay = days[currentTime.getDay()];
    const formattedTime = currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return (
        <div className="flex flex-col items-center justify-center h-full text-stone-200">
            <h1 className="text-3xl font-bold mb-8 text-orange-200/65">Weekly Timer</h1>

            <div className="bg-stone-800/40 backdrop-blur-lg border border-white/10 rounded-2xl p-10 flex flex-col items-center shadow-xl shadow-black/20">
                <div className="text-2xl font-medium text-amber-700 mb-2">{currentDay}</div>
                <div className="text-6xl font-bold text-stone-100 tracking-wider">{formattedTime}</div>
            </div>

            <div className="mt-12 text-stone-500 italic">
                Weekly schedule controls coming soon...
            </div>
        </div>
    );
};

export default WeeklyTimerView;
