import React from 'react';

interface BrandedTutorialIconProps {
  className?: string;
}

export const BrandedTutorialIcon: React.FC<BrandedTutorialIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {/* Book background */}
      <rect x="4" y="4" width="16" height="17" rx="1.5" fill="#26A69A" opacity="0.15" />

      {/* Book outline */}
      <path
        d="M4 5.5C4 4.67157 4.67157 4 5.5 4H18.5C19.3284 4 20 4.67157 20 5.5V18.5C20 19.3284 19.3284 20 18.5 20H5.5C4.67157 20 4 19.3284 4 18.5V5.5Z"
        stroke="#26A69A"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Book spine/middle line */}
      <line x1="12" y1="4" x2="12" y2="20" stroke="#26A69A" strokeWidth="1.5" />

      {/* Bookmark */}
      <path
        d="M15 2L15 9L17 7L19 9L19 2L15 2Z"
        fill="#FF6F00"
        stroke="#FF6F00"
        strokeWidth="0.5"
        strokeLinejoin="round"
      />

      {/* Light bulb/learning icon */}
      <circle cx="8" cy="10" r="2.5" fill="none" stroke="#FF6F00" strokeWidth="1.5" />
      <path d="M8 12.5 L8 14" stroke="#FF6F00" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="7" y1="14.5" x2="9" y2="14.5" stroke="#FF6F00" strokeWidth="1.5" strokeLinecap="round" />

      {/* Book pages decoration */}
      <path d="M7 16H10" stroke="#26A69A" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
      <path d="M14 16H17" stroke="#26A69A" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
    </svg>
  );
};
