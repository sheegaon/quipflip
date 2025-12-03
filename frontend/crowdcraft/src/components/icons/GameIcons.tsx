import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

interface TrophyIconProps extends IconProps {
  primaryColor?: string;
  secondaryColor?: string;
  accentColor?: string;
}

export const TrophyIcon: React.FC<TrophyIconProps> = ({
  className = 'w-8 h-8',
  primaryColor = '#FFC857',
  secondaryColor = '#10B5A4',
  accentColor = '#0E6F6A',
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    {/* Trophy cup */}
    <path
      d="M7 3h10v6c0 2.8-2.2 5-5 5s-5-2.2-5-5V3z"
      fill={primaryColor}
    />
    {/* Trophy handles */}
    <path
      d="M6 5H4c-1.1 0-2 .9-2 2v1c0 1.1.9 2 2 2h2V5zM18 5h2c1.1 0 2 .9 2 2v1c0 1.1-.9 2-2 2h-2V5z"
      fill={secondaryColor}
    />
    {/* Trophy base */}
    <rect x={8} y={14} width={8} height={2} fill={accentColor} />
    <path
      d="M7 16h10v2c0 1.1-.9 2-2 2H9c-1.1 0-2-.9-2-2v-2z"
      fill={primaryColor}
    />
    {/* Trophy stem */}
    <rect x={10.5} y={12} width={3} height={2} fill={accentColor} />
  </svg>
);
