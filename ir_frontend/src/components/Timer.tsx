import React, { useState, useEffect } from 'react';
import { getRemainingTime, formatCountdown } from '../utils/datetime';

interface TimerProps {
  targetTime: string;
  onExpire?: () => void;
  className?: string;
}

const Timer: React.FC<TimerProps> = ({ targetTime, onExpire, className = '' }) => {
  const [timeLeft, setTimeLeft] = useState(getRemainingTime(targetTime));

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = getRemainingTime(targetTime);
      setTimeLeft(remaining);

      if (remaining.isExpired && onExpire) {
        onExpire();
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [targetTime, onExpire]);

  if (timeLeft.isExpired) {
    return <div className={`text-red-500 font-mono ${className}`}>Expired</div>;
  }

  return (
    <div className={`font-mono ${className}`}>
      {formatCountdown(timeLeft.minutes, timeLeft.seconds)}
    </div>
  );
};

export default Timer;
