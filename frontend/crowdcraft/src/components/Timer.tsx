import React, { useEffect, useRef } from 'react';
import { useTimer, formatTime } from '../hooks/useTimer.ts';

export interface TimerProps {
  expiresAt: string | null;
  onExpired?: () => void;
  compact?: boolean;
}

export const Timer: React.FC<TimerProps> = ({ expiresAt, onExpired, compact = false }) => {
  const { timeRemaining, isExpired, isWarning, isUrgent } = useTimer(expiresAt);
  const hasFiredExpired = useRef(false);

  useEffect(() => {
    hasFiredExpired.current = false;
  }, [expiresAt]);

  useEffect(() => {
    if (!onExpired) return;
    if (isExpired && !hasFiredExpired.current) {
      hasFiredExpired.current = true;
      onExpired();
    }
  }, [isExpired, onExpired, expiresAt, timeRemaining]);

  if (!expiresAt) return null;

  const getTimerClass = () => {
    if (compact) {
      if (isExpired) return 'bg-orange-600 text-white';
      if (isUrgent) return 'bg-orange-500 text-white';
      if (isWarning) return 'bg-orange-400 text-white';
      return 'bg-orange-300 text-orange-900';
    }

    if (isExpired) return 'bg-red-600 text-white';
    if (isUrgent) return 'bg-red-500 text-white animate-pulse';
    if (isWarning) return 'bg-yellow-500 text-white';
    return 'bg-blue-500 text-white';
  };

  const baseClass = compact
    ? 'inline-flex items-center rounded-md px-3 py-1 text-sm font-semibold'
    : 'px-6 py-3 rounded-lg font-bold text-2xl';

  const displayValue = isExpired ? (compact ? '0:00' : "Time's Up!") : formatTime(timeRemaining);

  return (
    <div className={`${baseClass} ${getTimerClass()}`}>
      {displayValue}
    </div>
  );
};

export default Timer;
