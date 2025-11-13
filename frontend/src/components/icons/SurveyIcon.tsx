import React from 'react';

interface SurveyIconProps {
  className?: string;
}

export const SurveyIcon: React.FC<SurveyIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {/* Clipboard background */}
      <rect x="5" y="3" width="14" height="18" rx="2" fill="#26A69A" opacity="0.15" />
      <path
        d="M5 5C5 3.89543 5.89543 3 7 3H17C18.1046 3 19 3.89543 19 5V19C19 20.1046 18.1046 21 17 21H7C5.89543 21 5 20.1046 5 19V5Z"
        stroke="#26A69A"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Clip top */}
      <rect x="9" y="1" width="6" height="4" rx="1" fill="#FF6F00" />

      {/* Survey lines with checkmarks */}
      <path d="M8 9H16" stroke="#26A69A" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="9" cy="9" r="1" fill="#FF6F00" />

      <path d="M8 13H16" stroke="#26A69A" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="9" cy="13" r="1" fill="#FF6F00" />

      <path d="M8 17H14" stroke="#26A69A" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="9" cy="17" r="1" fill="#FF6F00" />
    </svg>
  );
};
