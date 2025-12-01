import React from 'react';

interface SimpleIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

interface AdminIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const AdminIcon: React.FC<AdminIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#FF6F00',
  accentColor = '#26A69A',
  backgroundOpacity = 0.15,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <path d="M12 2L4 6V11C4 16 7 20.5 12 22C17 20.5 20 16 20 11V6L12 2Z" fill={primaryColor} opacity={backgroundOpacity} />
    <path
      d="M12 2L4 6V11C4 16 7 20.5 12 22C17 20.5 20 16 20 11V6L12 2Z"
      stroke={primaryColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M12 8L13.236 10.764L16 12L13.236 13.236L12 16L10.764 13.236L8 12L10.764 10.764L12 8Z"
      fill={accentColor}
      stroke={accentColor}
      strokeWidth={1}
      strokeLinejoin="round"
    />
  </svg>
);

interface HomeIconProps extends SimpleIconProps {
  strokeColor?: string;
}

export const HomeIcon: React.FC<HomeIconProps> = ({ className = 'h-5 w-5', strokeColor = 'currentColor', ...props }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke={strokeColor} aria-hidden="true" {...props}>
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
    />
  </svg>
);

interface LeaderboardIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
  accentOpacity?: number;
}

export const LeaderboardIcon: React.FC<LeaderboardIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  accentColor = '#FF6F00',
  backgroundOpacity = 0.1,
  accentOpacity = 0.7,
  ...props
}) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <rect x={8} y={14} width={4} height={10} rx={1} fill={primaryColor} />
    <rect x={14} y={10} width={4} height={14} rx={1} fill={primaryColor} />
    <rect x={20} y={18} width={4} height={6} rx={1} fill={primaryColor} />
    <rect x={15} y={11} width={2} height={2} rx={0.5} fill={accentColor} opacity={accentOpacity} />
  </svg>
);

interface LobbyIconProps extends SimpleIconProps {
  primaryColor?: string;
  backgroundOpacity?: number;
}

export const LobbyIcon: React.FC<LobbyIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  backgroundOpacity = 0.1,
  ...props
}) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <circle cx={10} cy={13} r={2.5} fill={primaryColor} />
    <path d="M6 23C6 19.5 7.5 18 10 18C12.5 18 14 19.5 14 23" stroke={primaryColor} strokeWidth={2} strokeLinecap="round" fill="none" />
    <circle cx={16} cy={12} r={3} fill={primaryColor} />
    <path d="M11 24C11 20 12.5 18.5 16 18.5C19.5 18.5 21 20 21 24" stroke={primaryColor} strokeWidth={2} strokeLinecap="round" fill="none" />
    <circle cx={22} cy={13} r={2.5} fill={primaryColor} />
    <path d="M18 23C18 19.5 19.5 18 22 18C24.5 18 26 19.5 26 23" stroke={primaryColor} strokeWidth={2} strokeLinecap="round" fill="none" />
  </svg>
);

interface SettingsIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const SettingsIcon: React.FC<SettingsIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  accentColor = '#FF6F00',
  backgroundOpacity = 0.2,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <path
      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      fill={primaryColor}
      opacity={backgroundOpacity}
    />
    <path
      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      stroke={primaryColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx={12} cy={12} r={3} fill={accentColor} />
    <circle cx={12} cy={12} r={3} stroke={accentColor} strokeWidth={1.5} />
  </svg>
);

interface StatisticsIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  accentOpacity?: number;
}

export const StatisticsIcon: React.FC<StatisticsIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  accentColor = '#FF6F00',
  accentOpacity = 0.7,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <rect x={4} y={14} width={4} height={6} rx={1} fill={primaryColor} />
    <rect x={10} y={10} width={4} height={10} rx={1} fill={primaryColor} />
    <rect x={16} y={6} width={4} height={14} rx={1} fill={primaryColor} />
    <path d="M5 16L11 12L17 8" stroke={accentColor} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" opacity={accentOpacity} />
    <circle cx={5} cy={16} r={1.5} fill={accentColor} />
    <circle cx={11} cy={12} r={1.5} fill={accentColor} />
    <circle cx={17} cy={8} r={1.5} fill={accentColor} />
  </svg>
);

interface SurveyIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const SurveyIcon: React.FC<SurveyIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  accentColor = '#FF6F00',
  backgroundOpacity = 0.15,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <rect x={5} y={3} width={14} height={18} rx={2} fill={primaryColor} opacity={backgroundOpacity} />
    <path
      d="M5 5C5 3.895 5.895 3 7 3H17C18.105 3 19 3.895 19 5V19C19 20.105 18.105 21 17 21H7C5.895 21 5 20.105 5 19V5Z"
      stroke={primaryColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <rect x={9} y={1} width={6} height={4} rx={1} fill={accentColor} />
    <path d="M8 9H16" stroke={primaryColor} strokeWidth={1.5} strokeLinecap="round" />
    <circle cx={9} cy={9} r={1} fill={accentColor} />
    <path d="M8 13H16" stroke={primaryColor} strokeWidth={1.5} strokeLinecap="round" />
    <circle cx={9} cy={13} r={1} fill={accentColor} />
    <path d="M8 17H14" stroke={primaryColor} strokeWidth={1.5} strokeLinecap="round" />
    <circle cx={9} cy={17} r={1} fill={accentColor} />
  </svg>
);

interface TrackingIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const TrackingIcon: React.FC<TrackingIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#0B2137',
  accentColor = '#26A69A',
  backgroundOpacity = 0.1,
  ...props
}) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <path
      d="M16 6C12.686 6 10 8.686 10 12C10 13.857 10.838 15.519 12.167 16.583V20C12.167 20.921 12.913 21.667 13.833 21.667H18.167C19.087 21.667 19.833 20.921 19.833 20V16.583C21.162 15.519 22 13.857 22 12C22 8.686 19.314 6 16 6Z"
      fill={primaryColor}
    />
    <path d="M14 23.333C14 23.702 14.299 24 14.667 24H17.333C17.702 24 18 23.702 18 23.333V22.333H14V23.333Z" fill={primaryColor} />
    <circle cx={16} cy={12} r={2} fill={accentColor} />
  </svg>
);

interface CircleIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const CircleIcon: React.FC<CircleIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#10B4A4',
  accentColor = '#FF9A3D',
  backgroundOpacity = 0.12,
  ...props
}) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
    {/* Background circle */}
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />

    {/* Center celebration burst */}
    <circle cx={16} cy={16} r={4} fill={accentColor} opacity={0.3} />

    {/* Confetti/celebration elements in a circular pattern */}
    {/* Top */}
    <rect x={15} y={5} width={2} height={4} rx={1} fill={primaryColor} transform="rotate(0 16 7)" />
    {/* Top-right */}
    <rect x={23} y={8} width={2} height={4} rx={1} fill={accentColor} transform="rotate(45 24 10)" />
    {/* Right */}
    <circle cx={25} cy={16} r={1.5} fill={primaryColor} />
    {/* Bottom-right */}
    <rect x={22} y={20} width={2} height={4} rx={1} fill={accentColor} transform="rotate(-45 23 22)" />
    {/* Bottom */}
    <rect x={15} y={23} width={2} height={4} rx={1} fill={primaryColor} transform="rotate(0 16 25)" />
    {/* Bottom-left */}
    <rect x={8} y={20} width={2} height={4} rx={1} fill={accentColor} transform="rotate(45 9 22)" />
    {/* Left */}
    <circle cx={7} cy={16} r={1.5} fill={primaryColor} />
    {/* Top-left */}
    <rect x={9} y={8} width={2} height={4} rx={1} fill={accentColor} transform="rotate(-45 10 10)" />

    {/* Inner sparkle stars */}
    <path d="M16 11L16.5 13L18 13.5L16.5 14L16 16L15.5 14L14 13.5L15.5 13L16 11Z" fill={accentColor} />
    <path d="M20 15L20.3 16L21 16.3L20.3 16.6L20 18L19.7 16.6L19 16.3L19.7 16L20 15Z" fill={primaryColor} />
    <path d="M12 17L12.3 18L13 18.3L12.3 18.6L12 20L11.7 18.6L11 18.3L11.7 18L12 17Z" fill={primaryColor} />
  </svg>
);
