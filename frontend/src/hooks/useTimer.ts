import { useState, useEffect, useCallback } from 'react';

interface TimerState {
  timeRemaining: number;
  isExpired: boolean;
  isWarning: boolean;
  isUrgent: boolean;
}

export const useTimer = (expiresAt: string | null): TimerState => {
  const [timeRemaining, setTimeRemaining] = useState(0);

  const calculateTimeRemaining = useCallback(() => {
    if (!expiresAt) return 0;
    const now = new Date().getTime();
    const expiry = new Date(expiresAt).getTime();
    const remaining = Math.max(0, Math.floor((expiry - now) / 1000));
    return remaining;
  }, [expiresAt]);

  useEffect(() => {
    if (!expiresAt) {
      setTimeRemaining(0);
      return;
    }

    // Initial calculation
    setTimeRemaining(calculateTimeRemaining());

    // Update every second
    const interval = setInterval(() => {
      setTimeRemaining(calculateTimeRemaining());
    }, 1000);

    return () => clearInterval(interval);
  }, [expiresAt, calculateTimeRemaining]);

  return {
    timeRemaining,
    isExpired: timeRemaining === 0,
    isWarning: timeRemaining > 0 && timeRemaining <= 10,
    isUrgent: timeRemaining > 0 && timeRemaining <= 5,
  };
};

export const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};
