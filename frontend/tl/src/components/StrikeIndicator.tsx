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
    <div className="tile-card p-6">
      <div className="flex justify-center items-center gap-4">
        {strikeIndices.map((index) => (
          <div
            key={index}
            className={`
              w-12 h-12 rounded-full flex items-center justify-center
              font-display font-bold text-lg transition-all
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
        <p className="text-center text-ccl-teal mt-4 text-sm">
          {normalizedStrikes}/{maxStrikes} strikes · {maxStrikes - normalizedStrikes} remaining
        </p>
      )}
    </div>
  );
};

export default StrikeIndicator;
