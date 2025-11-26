import { useCallback, useEffect, useRef } from 'react';

interface ExponentialBackoffOptions {
  baseDelay?: number;
  maxDelay?: number;
}

export const useExponentialBackoff = (
  { baseDelay = 2000, maxDelay = 30000 }: ExponentialBackoffOptions = {}
) => {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef(0);

  const clear = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const resetAttempts = useCallback(() => {
    attemptsRef.current = 0;
    clear();
  }, [clear]);

  const schedule = useCallback(
    (callback: () => void) => {
      clear();
      const attempt = attemptsRef.current;
      const delay = Math.min(maxDelay, baseDelay * Math.pow(2, attempt));

      attemptsRef.current += 1;
      timeoutRef.current = setTimeout(() => {
        callback();
      }, delay);
    },
    [baseDelay, clear, maxDelay]
  );

  useEffect(() => () => clear(), [clear]);

  return { schedule, clear, resetAttempts };
};

export default useExponentialBackoff;
