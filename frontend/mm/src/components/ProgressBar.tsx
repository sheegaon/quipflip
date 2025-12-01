import React from 'react';

interface ProgressBarProps {
  current: number;
  max: number;
  thirdVote?: number;
  fifthVote?: number;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  current,
  max,
  thirdVote = 3,
  fifthVote = 5,
  className,
}) => {
  const safeMax = Math.max(max, 1);
  const percentage = Math.min(100, Math.round((current / safeMax) * 100));

  const markerPosition = (threshold: number) =>
    `${Math.min(100, Math.round((threshold / safeMax) * 100))}%`;

  return (
    <div className={`w-full ${className ?? ''}`}>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{current} / {max} votes</span>
        <span>{max - current} remaining</span>
      </div>
      <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
        {thirdVote && thirdVote < max && (
          <div
            className="absolute top-0 bottom-0 w-px bg-amber-400"
            style={{ left: markerPosition(thirdVote) }}
          >
            <span className="absolute -top-5 -translate-x-1/2 text-[10px] text-amber-600 font-semibold">
              3 votes
            </span>
          </div>
        )}
        {fifthVote && fifthVote < max && (
          <div
            className="absolute top-0 bottom-0 w-px bg-purple-400"
            style={{ left: markerPosition(fifthVote) }}
          >
            <span className="absolute -top-5 -translate-x-1/2 text-[10px] text-purple-600 font-semibold">
              5 votes
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
