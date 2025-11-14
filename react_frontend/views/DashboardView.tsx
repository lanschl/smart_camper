import React, { useRef, useEffect } from 'react';
import { VanState } from '../types';
import SensorCard from '../components/SensorCard';
import { WaterDropIcon, TemperatureIcon, BatteryIcon } from '../components/Icons';

// --- New Physics-based Water Tank Animation ---

// A class to represent a single segment of the water surface
class WaterColumn {
    // Target height is the resting position
    targetHeight: number;
    // Current height
    y: number;
    // Vertical velocity
    vy: number;

    constructor(targetHeight: number) {
        this.targetHeight = targetHeight;
        this.y = targetHeight;
        this.vy = 0;
    }

    // Update the column's physics based on tension and damping
    update(damping: number, tension: number) {
        if(this.y === undefined) return;
        const displacement = this.y - this.targetHeight;
        const acceleration = -tension * displacement - this.vy * damping;

        this.vy += acceleration;
        this.y += this.vy;
    }
}

interface PhysicsWaterTankProps {
    level: number;
    color: string;
}

const PhysicsWaterTank: React.FC<PhysicsWaterTankProps> = ({ level, color }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        
        const parent = canvas.parentElement;
        if (!parent) return;

        // Set canvas resolution to match its container size
        const rect = parent.getBoundingClientRect();
        if (rect.width === 0) return; // Safeguard against race condition
        canvas.width = rect.width;
        canvas.height = rect.height;
        
        const { width, height } = canvas;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Physics constants for the simulation
        const TENSION = 0.005;
        const DAMPING = 0.005;
        const SPREAD = 0.05;
        const NUM_COLUMNS = Math.floor(width / 4);

        const waterBaseLevel = height * (1 - level / 100);
        const columns: WaterColumn[] = [];

        for (let i = 0; i < NUM_COLUMNS; i++) {
            columns.push(new WaterColumn(waterBaseLevel));
        }
        
        const updateWater = () => {
            for (const column of columns) {
                column.update(DAMPING, TENSION);
            }

            const leftDeltas = new Array(NUM_COLUMNS).fill(0);
            const rightDeltas = new Array(NUM_COLUMNS).fill(0);

            for (let j = 0; j < 5; j++) { // Run simulation multiple times for stability
                for (let i = 0; i < NUM_COLUMNS; i++) {
                    if (i > 0) {
                        leftDeltas[i] = SPREAD * (columns[i].y - columns[i - 1].y);
                        columns[i - 1].vy += leftDeltas[i];
                    }
                    if (i < NUM_COLUMNS - 1) {
                        rightDeltas[i] = SPREAD * (columns[i].y - columns[i + 1].y);
                        columns[i + 1].vy += rightDeltas[i];
                    }
                }

                for (let i = 0; i < NUM_COLUMNS; i++) {
                    if (i > 0) columns[i - 1].y += leftDeltas[i];
                    if (i < NUM_COLUMNS - 1) columns[i + 1].y += rightDeltas[i];
                }
            }
        };

        const draw = () => {
            ctx.clearRect(0, 0, width, height);

            const gradient = ctx.createLinearGradient(0, waterBaseLevel - 50, 0, height);
            
            const [r, g, b] = color.match(/\w\w/g)!.map(hex => parseInt(hex, 16));
            gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.8)`);
            gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0.9)`);
            ctx.fillStyle = gradient;

            ctx.beginPath();
            ctx.moveTo(0, height);
            
            // FIX: Handle case where there are no columns to draw (e.g., canvas is too small)
            if (NUM_COLUMNS <= 0) {
                ctx.lineTo(0, waterBaseLevel);
                ctx.lineTo(width, waterBaseLevel);
            } else {
                let prevX = 0;
                let prevY = columns[0].y;
                ctx.lineTo(prevX, prevY);

                for (let i = 1; i < NUM_COLUMNS; i++) {
                    const x = (i / (NUM_COLUMNS - 1)) * width;
                    const y = columns[i].y;
                    
                    const midX = (prevX + x) / 2;
                    const midY = (prevY + y) / 2;
                    
                    ctx.quadraticCurveTo(prevX, prevY, midX, midY);

                    prevX = x;
                    prevY = y;
                }
                
                ctx.lineTo(width, columns[NUM_COLUMNS - 1].y);
            }
            
            ctx.lineTo(width, height);
            ctx.closePath();
            ctx.fill();
        };
        
        let animationFrameId: number;
        let time = 0;
        
        const animate = () => {
            const sloshAmount = 10;
            const sloshSpeed = 0.02;
            const tilt = Math.sin(time * sloshSpeed) * sloshAmount;

            for (let i = 0; i < NUM_COLUMNS; i++) {
                const columnTilt = ((i / NUM_COLUMNS) - 0.5) * tilt;
                columns[i].targetHeight = waterBaseLevel + columnTilt;
            }

            if (Math.random() < 0.005) {
                const randomColumnIndex = Math.floor(Math.random() * NUM_COLUMNS);
                columns[randomColumnIndex].vy = -5; 
            }

            updateWater();
            draw();
            
            time++;
            animationFrameId = requestAnimationFrame(animate);
        };

        const handleCanvasClick = (event: MouseEvent) => {
            const clickRect = canvas.getBoundingClientRect();
            const clickX = event.clientX - clickRect.left;
            const columnIndex = Math.floor((clickX / width) * NUM_COLUMNS);
            
            if (columnIndex >= 0 && columnIndex < NUM_COLUMNS) {
                columns[columnIndex].vy = -20;
            }
        };

        canvas.addEventListener('mousedown', handleCanvasClick);
        animate();

        return () => {
            cancelAnimationFrame(animationFrameId);
            canvas.removeEventListener('mousedown', handleCanvasClick);
        };
    }, [level, color]);

    return <canvas ref={canvasRef} className="w-full h-full block cursor-pointer" aria-label="Interactive animated water tank" />;
};


const getBatteryColor = (soc: number): string => {
    if (soc < 20) return 'text-red-500'; // Critical
    if (soc < 40) return 'text-amber-500'; // Warning
    return 'text-amber-700'; // Good
};

const LineChart: React.FC<{ data: { time: number; temp: number }[], chartColor: string }> = ({ data, chartColor }) => {
    if (!data || data.length < 2) return <div className="text-center text-stone-500">Not enough data for chart</div>;

    const width = 300;
    const height = 100;
    const padding = 5;

    const minTemp = Math.min(...data.map(d => d.temp));
    const maxTemp = Math.max(...data.map(d => d.temp));
    const startTime = data[0].time;
    const endTime = data[data.length - 1].time;

    const getX = (time: number) => ((time - startTime) / (endTime - startTime)) * (width - padding * 2) + padding;
    const getY = (temp: number) => height - padding - ((temp - minTemp) / (maxTemp - minTemp)) * (height - padding * 2);

    const pathData = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(d.time)} ${getY(d.temp)}`).join(' ');
    
    const areaPathData = `${pathData} V ${height} L ${padding} ${height} Z`;
    
    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
            <defs>
                <linearGradient id="areaGradient" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor={chartColor} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={chartColor} stopOpacity="0" />
                </linearGradient>
            </defs>
            <path d={areaPathData} fill="url(#areaGradient)" className="transition-all duration-500 ease-in-out" />
            <path d={pathData} fill="none" stroke={chartColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-all duration-500 ease-in-out" />
        </svg>
    );
};

const BatteryStatus: React.FC<{ soc: number; voltage: number; amperage: number; power: number; }> = ({ soc, voltage, amperage, power }) => {
    const radius = 58;
    const stroke = 12;
    const circumference = radius * 2 * Math.PI;
    const strokeDashoffset = circumference - (soc / 100) * circumference;

    const batteryColorClass = getBatteryColor(soc);
    const amperageColor = amperage >= 0 ? 'text-green-500' : 'text-red-500';
    // Power is also charging (green) or discharging (red)
    const powerColor = power >= 0 ? 'text-green-500' : 'text-red-500';

    return (
        <div className="flex flex-col items-center w-full">
            <div className="relative w-48 h-48">
                {/* ... (the SVG for the SOC circle is the same) ... */}
                <svg
                    height="100%"
                    width="100%"
                    viewBox="0 0 140 140"
                    className="-rotate-90"
                >
                    <circle
                        className="text-stone-600"
                        stroke="currentColor"
                        strokeWidth={stroke}
                        fill="transparent"
                        r={radius}
                        cx="70"
                        cy="70"
                    />
                    <circle
                        className={`${batteryColorClass} transition-colors duration-500`}
                        stroke="currentColor"
                        strokeWidth={stroke}
                        strokeDasharray={circumference}
                        style={{ strokeDashoffset, transition: 'stroke-dashoffset 0.5s ease-out' }}
                        strokeLinecap="round"
                        fill="transparent"
                        r={radius}
                        cx="70"
                        cy="70"
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-5xl font-bold text-stone-100`}>
                        {Math.round(soc)}
                        <span className="text-3xl">%</span>
                    </span>
                </div>
            </div>
            {/* --- THIS IS THE MODIFIED SECTION --- */}
            <div className="grid grid-cols-3 gap-2 w-full mt-2 text-center">
                <div>
                    <p className="text-sm text-stone-100">Voltage</p>
                    <p className="text-lg font-semibold text-stone-200">{voltage.toFixed(1)}V</p>
                </div>
                <div>
                    <p className="text-sm text-stone-100">Current</p>
                    <p className={`text-lg font-semibold ${amperageColor}`}>{amperage.toFixed(1)}A</p>
                </div>
                <div>
                    <p className="text-sm text-stone-100">Power</p>
                    <p className={`text-lg font-semibold ${powerColor}`}>{Math.round(power)}W</p>
                </div>
            </div>
        </div>
    );
};

/**
 * Calculates a smooth color gradient based on temperature.
 * @param temp The current temperature.
 * @returns An rgba color string for use in CSS.
 */
const getInterpolatedTempColor = (temp: number): string => {
    const minTemp = -15;
    const maxTemp = 90;
    
    // Start color: #9c9a9a (light gray)
    const startColor = { r: 250, g: 240, b: 210 };
    // End color: #450101 (dark red)
    const endColor = { r: 145, g: 17, b: 10 };

    // Calculate how far the temperature is along the scale (0 to 1)
    const tempRange = maxTemp - minTemp;
    const normalizedTemp = Math.max(0, Math.min(1, (temp - minTemp) / tempRange));

    // Interpolate each color channel
    const r = Math.round(startColor.r + (endColor.r - startColor.r) * normalizedTemp);
    const g = Math.round(startColor.g + (endColor.g - startColor.g) * normalizedTemp);
    const b = Math.round(startColor.b + (endColor.b - startColor.b) * normalizedTemp);
    
    // Return an rgba string with 50% opacity to maintain the glassy effect
    return `rgba(${r}, ${g}, ${b}, 0.8)`;
};


interface DashboardViewProps {
    sensors: VanState['sensors'];
}

const DashboardView: React.FC<DashboardViewProps> = ({ sensors }) => {
    
    const boilerChartColor = '#b45309'; // amber-700
    const tempValueClass = "text-stone-100 drop-shadow-sm";

    return (
    <div>
      <h1 className="text-3xl font-bold mb-4 text-orange-200/65">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="col-span-2">
            <SensorCard icon={<BatteryIcon className="w-6 h-6"/>} title="Battery Status" value="">
                <BatteryStatus soc={sensors.batterySoC} voltage={sensors.batteryVoltage} amperage={sensors.batteryAmperage} power={sensors.batteryPower} />
            </SensorCard>
        </div>
        <div className="col-span-2">
            <SensorCard 
                icon={<TemperatureIcon className="w-6 h-6"/>} 
                title="Boiler Temperature" 
                value={<span className={tempValueClass}>{`${sensors.boilerTemp}°C`}</span>}
                style={{ backgroundColor: getInterpolatedTempColor(sensors.boilerTemp) }}
            >
                <div className="w-full h-full max-h-40">
                    <LineChart data={sensors.boilerTempHistory} chartColor={boilerChartColor} />
                </div>
                <p className="text-sm text-center text-stone-400 mt-1">Last 12 Hours</p>
            </SensorCard>
        </div>
        
        <div className="col-span-1">
            <SensorCard 
                icon={<TemperatureIcon className="w-6 h-6"/>} 
                title="Cabin Temp" 
                value={<span className={tempValueClass}>{`${sensors.insideTemp.toFixed(1)}°C`}</span>}
                style={{ backgroundColor: getInterpolatedTempColor(sensors.insideTemp) }}
            />
        </div>

        <div className="col-span-1">
            <SensorCard 
                icon={<TemperatureIcon className="w-6 h-6"/>} 
                title="Outside Temp" 
                value={<span className={tempValueClass}>{`${sensors.outsideTemp.toFixed(1)}°C`}</span>}
                style={{ backgroundColor: getInterpolatedTempColor(sensors.outsideTemp) }}
            />
        </div>

        <div className="col-span-2">
            <SensorCard icon={<WaterDropIcon className="w-6 h-6"/>} title="Water Levels" value="">
                <div className="flex space-x-2 justify-center pt-2 w-full">
                    <div className="flex flex-col items-center w-1/2">
                        <div className="relative w-full h-24 bg-stone-500/75 rounded-lg overflow-hidden">
                            <PhysicsWaterTank level={sensors.freshWater} color="#0EA5E9" />
                            <span className="absolute bottom-1 left-0 right-0 text-center text-xl font-bold text-white pointer-events-none">{sensors.freshWater}%</span>
                        </div>
                        <span className="mt-1 text-sm text-stone-100">Fresh</span>
                    </div>
                    <div className="flex flex-col items-center w-1/2">
                         <div className="relative w-full h-24 bg-stone-500/75 rounded-lg overflow-hidden">
                            <PhysicsWaterTank level={sensors.grayWater} color="#D3D3D3" />
                            <span className="absolute bottom-1 left-0 right-0 text-center text-xl font-bold text-white pointer-events-none">{sensors.grayWater}%</span>
                        </div>
                        <span className="mt-1 text-sm text-stone-100">Gray</span>
                    </div>
                </div>
            </SensorCard>
        </div>

      </div>
    </div>
  );
};

export default DashboardView;