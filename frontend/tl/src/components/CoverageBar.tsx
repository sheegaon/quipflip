import React from 'react';

interface CoverageBarProps {
  coverage: number; // 0-100 percentage
  label?: string;
  showLabel?: boolean;
  animated?: boolean;
  height?: 'sm' | 'md' | 'lg';
}

export const CoverageBar: React.FC<CoverageBarProps> = ({
  coverage,
  label = 'Coverage',
  showLabel = true,
  animated = true,
  height = 'md',
}) => {
  // Clamp coverage to 0-100
  const normalizedCoverage = Math.min(Math.max(coverage, 0), 100);

  // Determine color gradient based on coverage level
  const getGradientClasses = () => {
    if (normalizedCoverage < 30) {
      return 'from-red-500 to-red-600';
    } else if (normalizedCoverage < 70) {
      return 'from-yellow-500 to-yellow-600';
    } else {
      return 'from-ccl-orange to-ccl-orange-deep';
    }
  };

  const heightClasses = {
    sm: 'h-2',
    md: 'h-4',
    lg: 'h-6',
  };

  return (
    <div className="tile-card p-6">
      {showLabel && (
        <div className="flex justify-between items-center gap-6 mb-2">
          <span className="font-semibold text-ccl-navy whitespace-nowrap">{label}</span>
          <span className="text-2xl font-display font-bold text-ccl-orange">
            {Math.round(normalizedCoverage)}%
          </span>
        </div>
      )}

      <div className={`w-full bg-gray-300 rounded-full ${heightClasses[height]} overflow-hidden`}>
        <div
          className={`
            h-full bg-gradient-to-r ${getGradientClasses()}
            ${animated ? 'transition-all duration-300' : ''}
          `}
          style={{ width: `${normalizedCoverage}%` }}
        />
      </div>
    </div>
  );
};

export default CoverageBar;
