import React from 'react';

interface ResultsIconProps {
  className?: string;
}

export const ResultsIcon: React.FC<ResultsIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Background circle */}
      <circle cx="16" cy="16" r="15" fill="#FF6F00" opacity="0.1" />

      {/* Trophy cup */}
      <path
        d="M10 12C10 10.8954 10.8954 10 12 10H20C21.1046 10 22 10.8954 22 12V14C22 16.2091 20.2091 18 18 18H14C11.7909 18 10 16.2091 10 14V12Z"
        fill="#FF6F00"
      />

      {/* Trophy base */}
      <rect x="14" y="18" width="4" height="3" fill="#FF6F00" />
      <rect x="11" y="21" width="10" height="2" rx="1" fill="#FF6F00" />

      {/* Star accent */}
      <circle cx="16" cy="13" r="1.5" fill="#26A69A" opacity="0.8" />
    </svg>
  );
};
