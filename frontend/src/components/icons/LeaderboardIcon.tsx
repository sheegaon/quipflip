import React from 'react';

interface LeaderboardIconProps {
  className?: string;
}

export const LeaderboardIcon: React.FC<LeaderboardIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Background circle */}
      <circle cx="16" cy="16" r="15" fill="#26A69A" opacity="0.1" />

      {/* Three bars in leaderboard/podium style: 2nd place (left), 1st place (center), 3rd place (right) */}
      <rect x="8" y="14" width="4" height="10" rx="1" fill="#26A69A" />
      <rect x="14" y="10" width="4" height="14" rx="1" fill="#26A69A" />
      <rect x="20" y="18" width="4" height="6" rx="1" fill="#26A69A" />

      {/* Accent on tallest bar (1st place in center) */}
      <rect x="15" y="11" width="2" height="2" rx="0.5" fill="#FF6F00" opacity="0.7" />
    </svg>
  );
};
