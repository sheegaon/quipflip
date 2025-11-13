import React, { useState, useEffect } from 'react';
import { LiveModeIcon, PracticeModeIcon } from './icons/RoundIcons';

interface ModeToggleProps {
  mode: 'live' | 'practice';
  onChange: (mode: 'live' | 'practice') => void;
}

export const ModeToggle: React.FC<ModeToggleProps> = ({ mode, onChange }) => {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 640);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 640);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Calculate transform value based on mode and screen size
  const getTransform = () => {
    if (mode === 'live') {
      return isMobile ? 'translateX(0rem)' : 'translateX(0)';
    }
    return isMobile ? 'translateX(2.5rem)' : 'translateX(2.375rem)';
  };

  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50">
      <div className="flex items-center gap-4">
        {/* Live Mode Label */}
        <button
          onClick={() => onChange('live')}
          className={`flex items-center gap-1 transition-opacity duration-200 ${
            mode === 'live' ? 'opacity-100' : 'opacity-60 hover:opacity-75'
          }`}
          aria-label="Switch to live mode"
        >
          <span className="font-bold text-quip-orange-deep">Live</span>
          <LiveModeIcon className="w-11 h-11" aria-hidden="true" />
        </button>

        {/* Toggle Switch */}
        <button
          role="switch"
          aria-checked={mode === 'practice'}
          aria-label={`Switch to ${mode === 'live' ? 'practice' : 'live'} mode`}
          onClick={() => onChange(mode === 'live' ? 'practice' : 'live')}
          className="relative w-20 sm:w-20 h-10 bg-white rounded-full shadow-tile-sm border-2 border-quip-navy border-opacity-10 focus:outline-none focus:ring-2 focus:ring-quip-teal focus:ring-offset-2"
          style={{
            width: isMobile ? '7rem' : '5rem',
            marginLeft: isMobile ? '0.75rem' : '0',
            marginRight: isMobile ? '-0.75rem' : '0'
          }}
        >
          {/* Slider Track Background */}
          <div className="absolute inset-0 rounded-full overflow-hidden pointer-events-none">
            <div
              className={`absolute inset-y-0 w-1/2 transition-all duration-300 ease-in-out ${
                mode === 'live' ? 'bg-quip-orange bg-opacity-20 left-0' : 'bg-quip-turquoise bg-opacity-20 right-0'
              }`}
            />
          </div>

          {/* Circular Button */}
          <div
            style={{
              transform: getTransform(),
              willChange: 'transform'
            }}
            className={`absolute top-1 left-1 w-7 h-7 rounded-full shadow-md transition-all duration-300 ease-in-out ${
              mode === 'live' ? 'bg-quip-orange' : 'bg-quip-turquoise'
            }`}
          />
        </button>

        {/* Practice Mode Label */}
        <button
          onClick={() => onChange('practice')}
          className={`flex items-center gap-1 transition-opacity duration-200 ${
            mode === 'practice' ? 'opacity-100' : 'opacity-60 hover:opacity-75'
          }`}
          aria-label="Switch to practice mode"
        >
          <PracticeModeIcon className="w-11 h-11" aria-hidden="true" />
          <span className="font-bold text-quip-turquoise">Practice</span>
        </button>
      </div>
    </div>
  );
};
