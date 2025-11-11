import React from 'react';

interface AdminIconProps {
  className?: string;
}

export const AdminIcon: React.FC<AdminIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {/* Shield shape */}
      <path
        d="M12 2L4 6V11C4 16 7 20.5 12 22C17 20.5 20 16 20 11V6L12 2Z"
        fill="#FF6F00"
        opacity="0.15"
      />
      <path
        d="M12 2L4 6V11C4 16 7 20.5 12 22C17 20.5 20 16 20 11V6L12 2Z"
        stroke="#FF6F00"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Star in center */}
      <path
        d="M12 8L13.236 10.764L16 12L13.236 13.236L12 16L10.764 13.236L8 12L10.764 10.764L12 8Z"
        fill="#26A69A"
        stroke="#26A69A"
        strokeWidth="1"
        strokeLinejoin="round"
      />
    </svg>
  );
};
