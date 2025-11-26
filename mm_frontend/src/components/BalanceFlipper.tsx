import React, { useEffect, useRef, useState } from 'react';

interface BalanceFlipperProps {
  value: number;
  className?: string;
}

const FLIP_DURATION = 500; // milliseconds
const HALF_DURATION = FLIP_DURATION / 2;

export const BalanceFlipper: React.FC<BalanceFlipperProps> = ({ value, className }) => {
  const [displayValue, setDisplayValue] = useState(value);
  const [isFlipping, setIsFlipping] = useState(false);
  const latestValueRef = useRef(value);
  const animationFrameRef = useRef<number>();

  useEffect(() => {
    if (value === latestValueRef.current) {
      return;
    }

    latestValueRef.current = value;

    if (animationFrameRef.current) {
      window.cancelAnimationFrame(animationFrameRef.current);
    }

    setIsFlipping(false);

    animationFrameRef.current = window.requestAnimationFrame(() => {
      animationFrameRef.current = undefined;
      setIsFlipping(true);
    });

    const halfTimeout = window.setTimeout(() => {
      setDisplayValue(latestValueRef.current);
    }, HALF_DURATION);

    const endTimeout = window.setTimeout(() => {
      setIsFlipping(false);
    }, FLIP_DURATION);

    return () => {
      if (animationFrameRef.current) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = undefined;
      }
      window.clearTimeout(halfTimeout);
      window.clearTimeout(endTimeout);
    };
  }, [value]);

  return (
    <span
      className={`balance-flip ${isFlipping ? 'balance-flip-active' : ''} ${className ?? ''}`.trim()}
    >
      {displayValue}
    </span>
  );
};

export default BalanceFlipper;
