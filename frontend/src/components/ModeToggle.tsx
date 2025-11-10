import React from 'react';

interface ModeToggleProps {
  mode: 'live' | 'practice';
  onChange: (mode: 'live' | 'practice') => void;
}

export const ModeToggle: React.FC<ModeToggleProps> = ({ mode, onChange }) => {
  return (
    <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40">
      <div className="tile-card p-2 flex items-center gap-2 shadow-tile">
        {/* Live Mode Button */}
        <button
          onClick={() => onChange('live')}
          className={`flex items-center gap-2 px-4 py-2 rounded-tile transition-all ${
            mode === 'live'
              ? 'bg-quip-orange text-white shadow-tile-sm'
              : 'bg-transparent text-quip-teal hover:bg-quip-orange hover:bg-opacity-10'
          }`}
        >
          <img
            src="/icon_live.svg"
            alt=""
            className="w-6 h-6"
            style={{ filter: mode === 'live' ? 'brightness(0) invert(1)' : 'none' }}
          />
          <span className="font-semibold">Live</span>
        </button>

        {/* Practice Mode Button */}
        <button
          onClick={() => onChange('practice')}
          className={`flex items-center gap-2 px-4 py-2 rounded-tile transition-all ${
            mode === 'practice'
              ? 'bg-quip-turquoise text-white shadow-tile-sm'
              : 'bg-transparent text-quip-teal hover:bg-quip-turquoise hover:bg-opacity-10'
          }`}
        >
          <img
            src="/icon_practice.svg"
            alt=""
            className="w-6 h-6"
            style={{ filter: mode === 'practice' ? 'brightness(0) invert(1)' : 'none' }}
          />
          <span className="font-semibold">Practice</span>
        </button>
      </div>
    </div>
  );
};
