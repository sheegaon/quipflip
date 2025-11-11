import React from 'react';

interface ModeToggleProps {
  mode: 'live' | 'practice';
  onChange: (mode: 'live' | 'practice') => void;
}

export const ModeToggle: React.FC<ModeToggleProps> = ({ mode, onChange }) => {
  return (
    <div className="fixed bottom-20 left-1/2 transform -translate-x-1/2 z-50">
      <div className="flex items-center gap-4">
        {/* Live Mode Label */}
        <button
          onClick={() => onChange('live')}
          className={`flex items-center gap-2 transition-all ${
            mode === 'live' ? 'opacity-100' : 'opacity-50 hover:opacity-75'
          }`}
          aria-label="Switch to live mode"
        >
          <img
            src="/icon_live.svg"
            alt=""
            className="w-6 h-6"
          />
          <span className="font-semibold text-quip-orange-deep">Live</span>
        </button>

        {/* Toggle Switch */}
        <button
          role="switch"
          aria-checked={mode === 'practice'}
          aria-label={`Switch to ${mode === 'live' ? 'practice' : 'live'} mode`}
          onClick={() => onChange(mode === 'live' ? 'practice' : 'live')}
          className="relative w-20 h-10 bg-white rounded-full shadow-tile-sm border-2 border-quip-navy border-opacity-10 transition-all focus:outline-none focus:ring-2 focus:ring-quip-teal focus:ring-offset-2"
        >
          {/* Slider Track Background */}
          <div className="absolute inset-0 rounded-full overflow-hidden pointer-events-none">
            <div
              className={`absolute inset-y-0 w-1/2 transition-all duration-300 ${
                mode === 'live' ? 'bg-quip-orange bg-opacity-20 left-0' : 'bg-quip-turquoise bg-opacity-20 right-0'
              }`}
            />
          </div>

          {/* Circular Button */}
          <div
            className={`absolute top-1 left-0.75 sm:left-1 w-7 h-7 rounded-full shadow-md transition-all duration-300 ${
              mode === 'live'
                ? 'translate-x-0 bg-quip-orange'
                : 'translate-x-[2rem] sm:translate-x-[2.375rem] bg-quip-turquoise'
            }`}
          />
        </button>

        {/* Practice Mode Label */}
        <button
          onClick={() => onChange('practice')}
          className={`flex items-center gap-2 transition-all ${
            mode === 'practice' ? 'opacity-100' : 'opacity-50 hover:opacity-75'
          }`}
          aria-label="Switch to practice mode"
        >
          <img
            src="/icon_practice.svg"
            alt=""
            className="w-6 h-6"
          />
          <span className="font-semibold text-quip-turquoise">Practice</span>
        </button>
      </div>
    </div>
  );
};
