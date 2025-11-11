import React from 'react';

interface TrophyIconProps {
  className?: string;
}

export const TrophyIcon: React.FC<TrophyIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 15v6m0 0H9m3 0h3M7 5h10a2 2 0 012 2v4a5 5 0 01-10 0V7a2 2 0 012-2zM5 7H4a2 2 0 00-2 2v2a2 2 0 002 2h1M19 7h1a2 2 0 012 2v2a2 2 0 01-2 2h-1"
      />
    </svg>
  );
};
