import React from 'react';

interface FrozenTimerProps {
  displayTime?: string;
}

export const FrozenTimer: React.FC<FrozenTimerProps> = ({ displayTime = '3:00' }) => {
  return (
    <div className="bg-quip-cream rounded-tile px-6 py-3 shadow-tile-sm">
      <div className="text-center">
        <span className="text-3xl font-display font-bold text-quip-navy">{displayTime}</span>
      </div>
    </div>
  );
};
