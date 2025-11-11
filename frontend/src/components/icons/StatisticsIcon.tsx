import React from 'react';

interface StatisticsIconProps {
  className?: string;
}

export const StatisticsIcon: React.FC<StatisticsIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {/* Three ascending bars */}
      <rect x="4" y="14" width="4" height="6" rx="1" fill="#26A69A" />
      <rect x="10" y="10" width="4" height="10" rx="1" fill="#26A69A" />
      <rect x="16" y="6" width="4" height="14" rx="1" fill="#26A69A" />

      {/* Trend line overlay */}
      <path
        d="M5 16L11 12L17 8"
        stroke="#FF6F00"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.7"
      />
      <circle cx="5" cy="16" r="1.5" fill="#FF6F00" />
      <circle cx="11" cy="12" r="1.5" fill="#FF6F00" />
      <circle cx="17" cy="8" r="1.5" fill="#FF6F00" />
    </svg>
  );
};
