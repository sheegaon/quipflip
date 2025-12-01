import React from 'react';

interface FrozenTimerProps {
  displayTime?: string;
}

export const FrozenTimer: React.FC<FrozenTimerProps> = ({ displayTime = '3:00' }) => {
  return (
    <div className="px-6 py-3 rounded-lg font-bold text-2xl bg-blue-500 text-white">
      {displayTime}
    </div>
  );
};
