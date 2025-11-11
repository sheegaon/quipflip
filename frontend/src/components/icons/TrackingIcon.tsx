import React from 'react';

interface TrackingIconProps {
  className?: string;
}

export const TrackingIcon: React.FC<TrackingIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Background circle */}
      <circle cx="16" cy="16" r="15" fill="#0B2137" opacity="0.1" />

      {/* Lightbulb body */}
      <path
        d="M16 6C12.6863 6 10 8.68629 10 12C10 13.8565 10.8384 15.5186 12.1667 16.5833V20C12.1667 20.9205 12.9128 21.6667 13.8333 21.6667H18.1667C19.0872 21.6667 19.8333 20.9205 19.8333 20V16.5833C21.1616 15.5186 22 13.8565 22 12C22 8.68629 19.3137 6 16 6Z"
        fill="#0B2137"
      />

      {/* Lightbulb base */}
      <path
        d="M14 23.3333C14 23.7015 14.2985 24 14.6667 24H17.3333C17.7015 24 18 23.7015 18 23.3333V22.3333H14V23.3333Z"
        fill="#0B2137"
      />

      {/* Accent circle (idea light) */}
      <circle cx="16" cy="12" r="2" fill="#26A69A" />
    </svg>
  );
};
