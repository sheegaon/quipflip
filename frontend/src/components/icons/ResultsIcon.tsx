import React from 'react';

interface ResultsIconProps {
  className?: string;
  variant?: 'orange' | 'teal';
}

export const ResultsIcon: React.FC<ResultsIconProps> = ({
  className = 'h-5 w-5',
  variant = 'orange'
}) => {
  // Define colors based on variant
  const colors = variant === 'teal'
    ? {
        primary: '#26A69A',  // Teal for trophy
        accent: '#FF6F00'    // Orange for star accent
      }
    : {
        primary: '#FF6F00',  // Orange for trophy
        accent: '#26A69A'    // Teal for star accent
      };

  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Background circle */}
      <circle cx="16" cy="16" r="15" fill={colors.primary} opacity="0.1" />

      {/* Trophy cup */}
      <path
        d="M10 12C10 10.8954 10.8954 10 12 10H20C21.1046 10 22 10.8954 22 12V14C22 16.2091 20.2091 18 18 18H14C11.7909 18 10 16.2091 10 14V12Z"
        fill={colors.primary}
      />

      {/* Trophy base */}
      <rect x="14" y="18" width="4" height="3" fill={colors.primary} />
      <rect x="11" y="21" width="10" height="2" rx="1" fill={colors.primary} />

      {/* Star accent */}
      <circle cx="16" cy="13" r="1.5" fill={colors.accent} opacity="0.8" />
    </svg>
  );
};
