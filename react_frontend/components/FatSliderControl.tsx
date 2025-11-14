
import React from 'react';

interface FatSliderControlProps {
  label: string;
  level: number;
  onChange: (level: number) => void;
  color: string;
  min?: number;
  max?: number;
  unit?: string;
}

const FatSliderControl: React.FC<FatSliderControlProps> = ({ label, level, onChange, color, min = 0, max = 100, unit = '%' }) => {
  const trackColor = '#57534e'; // stone-600
  const levelPercent = ((level - min) / (max - min)) * 100;
  const sliderBackground = `linear-gradient(to right, ${color} ${levelPercent}%, ${trackColor} ${levelPercent}%)`;

  return (
    <div className="w-full">
      <label className="text-base font-semibold text-stone-200">{label}</label>
      <div className="flex items-center space-x-4 mt-2">
        <input
            type="range"
            min={min}
            max={max}
            value={level}
            onChange={(e) => onChange(parseInt(e.target.value, 10))}
            className="custom-slider flex-grow rounded-lg"
            style={{ 
              background: sliderBackground,
            }}
        />
        <span className="text-lg font-semibold text-stone-200 w-16 text-right">{level}{unit}</span>
      </div>
    </div>
  );
};

export default FatSliderControl;