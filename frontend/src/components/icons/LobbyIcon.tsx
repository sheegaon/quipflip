import React from 'react';

interface LobbyIconProps {
  className?: string;
}

export const LobbyIcon: React.FC<LobbyIconProps> = ({ className = 'h-5 w-5' }) => {
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

      {/* Three user silhouettes representing online users */}

      {/* Left user */}
      <circle cx="10" cy="13" r="2.5" fill="#26A69A" />
      <path
        d="M6 23 C6 19.5 7.5 18 10 18 C12.5 18 14 19.5 14 23"
        stroke="#26A69A"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />

      {/* Center user (larger, emphasized) */}
      <circle cx="16" cy="12" r="3" fill="#26A69A" />
      <path
        d="M11 24 C11 20 12.5 18.5 16 18.5 C19.5 18.5 21 20 21 24"
        stroke="#26A69A"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />

      {/* Right user */}
      <circle cx="22" cy="13" r="2.5" fill="#26A69A" />
      <path
        d="M18 23 C18 19.5 19.5 18 22 18 C24.5 18 26 19.5 26 23"
        stroke="#26A69A"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
};
