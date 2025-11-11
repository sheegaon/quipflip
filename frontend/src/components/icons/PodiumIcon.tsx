import React from 'react';

interface PodiumIconProps {
  className?: string;
}

export const PodiumIcon: React.FC<PodiumIconProps> = ({ className = 'h-5 w-5' }) => {
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
        d="M9 3v6H5v12h4V9h6v12h4V9h-4V3H9z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 9h4M15 9h4M9 21h6"
      />
    </svg>
  );
};
