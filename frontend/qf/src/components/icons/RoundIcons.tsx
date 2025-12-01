import React from 'react';

interface RoundIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

interface CopyRoundIconProps extends RoundIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const CopyRoundIcon: React.FC<CopyRoundIconProps> = ({
  className = 'w-8 h-8',
  primaryColor = '#10B4A4',
  accentColor = '#FFF6EE',
  backgroundOpacity = 0.1,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <rect x={9} y={11} width={10} height={10} rx={2} fill={primaryColor} />
    <rect x={13} y={15} width={10} height={10} rx={2} fill={primaryColor} stroke={accentColor} strokeWidth={1.5} />
    <path d="M16 19L18 21L21 18" stroke={accentColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface VoteRoundIconProps extends RoundIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const VoteRoundIcon: React.FC<VoteRoundIconProps> = ({
  className = 'w-8 h-8',
  primaryColor = '#FF9A3D',
  accentColor = '#E26A00',
  backgroundOpacity = 0.1,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <circle cx={16} cy={16} r={10} stroke={primaryColor} strokeWidth={2} />
    <circle cx={16} cy={16} r={6} stroke={primaryColor} strokeWidth={2} />
    <circle cx={16} cy={16} r={3} fill={primaryColor} />
    <path d="M16 6V10M16 22V26M6 16H10M22 16H26" stroke={accentColor} strokeWidth={1.5} strokeLinecap="round" />
  </svg>
);

interface LiveModeIconProps extends RoundIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const LiveModeIcon: React.FC<LiveModeIconProps> = ({
  className = 'w-8 h-8',
  primaryColor = '#E26A00',
  accentColor = '#B54F00',
  backgroundOpacity = 0.15,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <path d="M8 16C8 11.5817 11.5817 8 16 8" stroke={primaryColor} strokeWidth={2.5} strokeLinecap="round" />
    <path d="M24 16C24 11.5817 20.4183 8 16 8" stroke={primaryColor} strokeWidth={2.5} strokeLinecap="round" />
    <path d="M11 16C11 13.2386 13.2386 11 16 11" stroke={primaryColor} strokeWidth={2.5} strokeLinecap="round" />
    <path d="M21 16C21 13.2386 18.7614 11 16 11" stroke={primaryColor} strokeWidth={2.5} strokeLinecap="round" />
    <circle cx={16} cy={16} r={3} fill={accentColor} />
  </svg>
);

interface PracticeModeIconProps extends RoundIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const PracticeModeIcon: React.FC<PracticeModeIconProps> = ({
  className = 'w-8 h-8',
  primaryColor = '#0A5852',
  accentColor = '#063D39',
  backgroundOpacity = 0.15,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <rect x={8} y={14} width={3} height={4} rx={1} fill={primaryColor} />
    <rect x={21} y={14} width={3} height={4} rx={1} fill={primaryColor} />
    <rect x={11} y={15} width={10} height={2} fill={primaryColor} />
    <path d="M16 8L17.5 11.5L21 12L18.5 15L19 18.5L16 16.5L13 18.5L13.5 15L11 12L14.5 11.5L16 8Z" fill={accentColor} />
  </svg>
);
