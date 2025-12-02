import React from 'react';

export interface ProgressBarProps {
  current: number;
  total: number;
  label?: string;
  showLabel?: boolean;
  className?: string;
  barClassName?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  current,
  total,
  label,
  showLabel = true,
  className = '',
  barClassName = '',
}) => {
  const progress = Math.min(Math.max((current / total) * 100, 0), 100);
  const displayLabel = label ?? `${current}/${total}`;

  return (
    <div className={`space-y-2 ${className}`}>
      {showLabel && <div className="text-sm text-gray-600">{displayLabel}</div>}
      <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
        <div
          className={`bg-gradient-to-r from-ccl-turquoise to-ccl-plum h-2.5 rounded-full transition-all duration-500 ${barClassName}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;
