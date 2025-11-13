import React from 'react';

interface ArrowIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  color?: string;
  strokeWidth?: number;
}

export const ArrowLeftIcon: React.FC<ArrowIconProps> = ({
  className = 'w-4 h-6',
  color = '#10B4A4',
  strokeWidth = 4.5,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 16 24"
    fill="none"
    className={className}
    {...props}
  >
    <path d="M12 20L4 12L12 4" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const ArrowRightIcon: React.FC<ArrowIconProps> = ({
  className = 'w-4 h-6',
  color = '#10B4A4',
  strokeWidth = 4.5,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 16 24"
    fill="none"
    className={className}
    {...props}
  >
    <path d="M4 4L12 12L4 20" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
