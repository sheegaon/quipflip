import React, { useEffect, useRef } from 'react';
import { useTimer, formatTime } from '../hooks/useTimer';

interface TimerProps {
  targetTime: string | null;
  onExpire?: () => void;
  compact?: boolean;
  className?: string;
}

const Timer: React.FC<TimerProps> = ({ targetTime, onExpire, compact = false, className = '' }) => {
  const { timeRemaining, isExpired, isWarning, isUrgent } = useTimer(targetTime);
  const hasFiredExpired = useRef(false);

  useEffect(() => {
    hasFiredExpired.current = false;
  }, [targetTime]);

  useEffect(() => {
    if (!onExpire) return;
    if (isExpired && !hasFiredExpired.current) {
      hasFiredExpired.current = true;
      onExpire();
    }
  }, [isExpired, onExpire, targetTime, timeRemaining]);

  if (!targetTime) return null;

  const getTimerClass = () => {
    if (compact) {
      if (isExpired) return 'bg-ir-orange-deep text-white';
      if (isUrgent) return 'bg-ir-orange text-white';
      if (isWarning) return 'bg-ir-orange-light text-ir-navy';
      return 'bg-ir-turquoise text-white';
    }

    if (isExpired) return 'bg-ir-orange-deep text-white';
    if (isUrgent) return 'bg-ir-orange text-white animate-pulse';
    if (isWarning) return 'bg-ir-orange-light text-ir-navy';
    return 'bg-ir-turquoise text-white';
  };

  const baseClass = compact
    ? 'inline-flex items-center rounded-tile px-3 py-1 text-sm font-semibold'
    : 'px-6 py-3 rounded-tile font-bold text-2xl';

  const displayValue = isExpired ? (compact ? '0:00' : "Time's Up!") : formatTime(timeRemaining);

  return (
    <div className={`${baseClass} ${getTimerClass()} ${className}`}>
      {displayValue}
    </div>
  );
};

export default Timer;
