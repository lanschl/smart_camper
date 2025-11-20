import React, { useState, useEffect } from 'react';
import { Socket } from 'socket.io-client';
import { ScheduleEntry, ScheduleState } from '../types';
import FatSliderControl from '../components/FatSliderControl';

const DAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']; // 0=Monday in Python

// --- Define Props Interface ---
interface WeeklyTimerViewProps {
    schedule: ScheduleState;
    socketRef: React.MutableRefObject<Socket | null>;
    onUpdate: (updateFn: (prevState: any) => any) => void;
}

const TimePicker: React.FC<{ value: string, onChange: (val: string) => void }> = ({ value, onChange }) => {
    const [hours, minutes] = value.split(':').map(Number);

    const adjust = (type: 'h' | 'm', amount: number) => {
        let newH = hours;
        let newM = minutes;

        if (type === 'h') {
            newH = (hours + amount + 24) % 24;
        } else {
            newM = (minutes + amount + 60) % 60;
        }

        const hStr = newH.toString().padStart(2, '0');
        const mStr = newM.toString().padStart(2, '0');
        onChange(`${hStr}:${mStr}`);
    };

    return (
        <div className="flex items-center gap-2">
            {/* Hours */}
            <div className="flex flex-col items-center">
                <button onClick={() => adjust('h', 1)} className="p-1 text-stone-400 hover:text-white text-xs">▲</button>
                <span className="text-xl font-bold text-stone-100">{hours.toString().padStart(2, '0')}</span>
                <button onClick={() => adjust('h', -1)} className="p-1 text-stone-400 hover:text-white text-xs">▼</button>
            </div>
            <span className="text-xl font-bold text-stone-500 pb-1">:</span>
            {/* Minutes */}
            <div className="flex flex-col items-center">
                <button onClick={() => adjust('m', 5)} className="p-1 text-stone-400 hover:text-white text-xs">▲</button>
                <span className="text-xl font-bold text-stone-100">{minutes.toString().padStart(2, '0')}</span>
                <button onClick={() => adjust('m', -5)} className="p-1 text-stone-400 hover:text-white text-xs">▼</button>
            </div>
        </div>
    );
};

const WeeklyTimerView: React.FC<WeeklyTimerViewProps> = ({ schedule, socketRef, onUpdate }) => {
    const [currentTime, setCurrentTime] = useState(new Date());

    // Clock
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const handleToggleGlobal = () => {
        const newState = !schedule.isEnabled;
        // Optimistic update via parent
        onUpdate(prevState => ({
            ...prevState,
            schedule: { ...prevState.schedule, isEnabled: newState }
        }));
        socketRef.current?.emit('diesel_heater_schedule_command', {
            command: 'set_timer_toggle',
            value: newState
        });
    };

    const handleAddTimer = () => {
        const newTimer: ScheduleEntry = {
            days: [0, 1, 2, 3, 4], // Mon-Fri default
            starttime: "08:00",
            endtime: "09:00",
            output: 22
        };
        const newTimers = [...schedule.timers, newTimer];
        updateSchedule(newTimers);
    };

    const handleRemoveTimer = (index: number) => {
        const newTimers = schedule.timers.filter((_, i) => i !== index);
        updateSchedule(newTimers);
    };

    const handleUpdateTimer = (index: number, updatedTimer: ScheduleEntry) => {
        const newTimers = [...schedule.timers];
        newTimers[index] = updatedTimer;
        updateSchedule(newTimers);
    };

    const updateSchedule = (timers: ScheduleEntry[]) => {
        // Optimistic update via parent
        onUpdate(prevState => ({
            ...prevState,
            schedule: { ...prevState.schedule, timers }
        }));
        socketRef.current?.emit('diesel_heater_schedule_command', {
            command: 'set_schedule',
            schedule: timers
        });
    };

    const toggleDay = (timerIndex: number, dayIndex: number) => {
        const timer = schedule.timers[timerIndex];
        const currentDays = timer.days;
        let newDays;
        if (currentDays.includes(dayIndex)) {
            newDays = currentDays.filter(d => d !== dayIndex);
        } else {
            newDays = [...currentDays, dayIndex].sort();
        }
        handleUpdateTimer(timerIndex, { ...timer, days: newDays });
    };

    // Date/Time formatting
    const dayName = currentTime.toLocaleDateString('en-GB', { weekday: 'long' });
    const day = currentTime.getDate().toString().padStart(2, '0');
    const month = currentTime.toLocaleDateString('en-GB', { month: 'short' });
    const formattedDateDay = `${dayName.toUpperCase()} ${day}. ${month.toUpperCase()}`;
    const formattedTime = currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-3xl font-bold text-orange-200/65">Weekly Schedule</h1>
                <div className="text-right">
                    <div className="text-2xl font-bold text-stone-100 flex items-end gap-3">
                        <span className="text-sm font-bold text-stone-100 pb-0.5 tracking-wide">
                            {formattedDateDay}
                        </span>
                        {formattedTime}
                    </div>
                </div>
            </div>

            <div className="bg-stone-800/40 backdrop-blur-lg border border-white/10 rounded-2xl p-6 mb-6 flex items-center justify-between shadow-lg">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">📅</span>
                    <div>
                        <h3 className="font-bold text-stone-100">Scheduler Active</h3>
                        <p className="text-sm text-stone-400">Enable automatic heating schedule</p>
                    </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                    <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={schedule.isEnabled}
                        onChange={handleToggleGlobal}
                    />
                    <div className="w-14 h-8 bg-stone-700 rounded-full peer peer-focus:ring-4 peer-focus:ring-amber-800 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-1 after:left-1 after:bg-white after:border-stone-600 after:border after:rounded-full after:h-6 after:w-6 after:transition-all after:duration-300 after:ease-in-out peer-checked:bg-amber-700 peer-checked:shadow-lg peer-checked:shadow-amber-800/40 transition-all duration-300 ease-in-out"></div>
                </label>
            </div>

            <div className="flex-grow overflow-y-auto space-y-4 pr-2">
                {schedule.timers.map((timer, index) => (
                    <div key={index} className="bg-stone-800/30 border border-white/5 rounded-xl p-4 transition-all hover:bg-stone-800/50">
                        <div className="flex justify-between items-start mb-4">
                            <div className="flex gap-1">
                                {DAYS.map((day, dayIndex) => (
                                    <button
                                        key={dayIndex}
                                        onClick={() => toggleDay(index, dayIndex)}
                                        className={`w-8 h-8 rounded-full text-xs font-bold transition-all ${timer.days.includes(dayIndex)
                                            ? 'bg-amber-700 text-white shadow-md'
                                            : 'bg-stone-700/50 text-stone-400 hover:bg-stone-600'
                                            }`}
                                    >
                                        {day}
                                    </button>
                                ))}
                            </div>
                            <button
                                onClick={() => handleRemoveTimer(index)}
                                className="text-stone-500 hover:text-red-400 transition-colors p-1"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="flex gap-4 items-center justify-center bg-stone-900/20 p-3 rounded-lg">
                                <div className="flex flex-col items-center">
                                    <label className="text-xs text-stone-500 mb-1 uppercase">Start</label>
                                    <TimePicker
                                        value={timer.starttime}
                                        onChange={(val) => handleUpdateTimer(index, { ...timer, starttime: val })}
                                    />
                                </div>
                                <span className="text-stone-600 text-xl pt-4">→</span>
                                <div className="flex flex-col items-center">
                                    <label className="text-xs text-stone-500 mb-1 uppercase">End</label>
                                    <TimePicker
                                        value={timer.endtime}
                                        onChange={(val) => handleUpdateTimer(index, { ...timer, endtime: val })}
                                    />
                                </div>
                            </div>

                            <div className="flex items-center">
                                <FatSliderControl
                                    label="Target Temp"
                                    level={timer.output}
                                    onChange={(val) => handleUpdateTimer(index, { ...timer, output: val })}
                                    min={18}
                                    max={30}
                                    unit="°C"
                                    color="#b45309"
                                />
                            </div>
                        </div>
                    </div>
                ))}

                <button
                    onClick={handleAddTimer}
                    className="w-full py-4 border-2 border-dashed border-stone-700 rounded-xl text-stone-500 hover:border-amber-700/50 hover:text-amber-700 hover:bg-amber-900/10 transition-all font-medium flex items-center justify-center gap-2"
                >
                    <span className="text-xl">+</span> Add New Timer
                </button>
            </div>
        </div>
    );
};

export default WeeklyTimerView;