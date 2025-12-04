import React from 'react';

interface StrikeIndicatorProps {
  strikes: number; // 0-3
  maxStrikes?: number;
  showLabel?: boolean;
  animated?: boolean;
}

export const StrikeIndicator: React.FC<StrikeIndicatorProps> = ({
  strikes,
  maxStrikes = 3,
  showLabel = true,
  animated = true,
}) => {
  // Clamp strikes to 0-maxStrikes
  const normalizedStrikes = Math.min(Math.max(strikes, 0), maxStrikes);
  const strikeIndices = Array.from({ length: maxStrikes }, (_, i) => i);

  return (
    <div className="tile-card p-4 sm:p-6 h-full flex flex-col justify-center">
      <div className="flex justify-center items-center gap-3 sm:gap-4">
        {strikeIndices.map((index) => (
          <div
            key={index}
            className={`
              w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center
              font-display font-bold text-base sm:text-lg transition-all
              ${
                index < normalizedStrikes
                  ? `bg-red-500 text-white ring-2 ring-red-700 ${animated ? 'animate-pulse' : ''}`
                  : 'bg-ccl-navy text-white border-2 border-ccl-navy'
              }
            `}
          >
            {index + 1}
          </div>
        ))}
      </div>

      {showLabel && (
        <p className="text-center text-ccl-teal mt-3 sm:mt-4 text-xs sm:text-sm">
          {normalizedStrikes}/{maxStrikes} strikes · {maxStrikes - normalizedStrikes} remaining
        </p>
      )}
    </div>
  );
};

export default StrikeIndicator;
