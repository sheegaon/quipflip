import React from 'react';

interface SimpleIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

interface FlagIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  color?: string;
  strokeWidth?: number | string;
}

interface TrophyIconProps extends SimpleIconProps {
  variant?: 'orange' | 'teal';
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

interface BotIconProps extends SimpleIconProps {
  primaryColor?: string;
  strokeColor?: string;
  detailColor?: string;
}

export const BotIcon: React.FC<BotIconProps> = ({
  className = 'h-4 w-4',
  primaryColor = '#FF9A3D',
  strokeColor = '#E26A00',
  detailColor = '#0B2137',
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-label="AI Player" {...props}>
    <rect x={5} y={6} width={14} height={13} rx={2} fill={primaryColor} stroke={strokeColor} strokeWidth={1} />
    <line x1={12} y1={3.5} x2={12} y2={6} stroke={primaryColor} strokeWidth={1.5} strokeLinecap="round" />
    <circle cx={12} cy={2.5} r={1.2} fill={primaryColor} stroke={strokeColor} strokeWidth={0.5} />
    <rect x={8} y={10} width={2.5} height={2.5} rx={0.5} fill={detailColor} />
    <rect x={13.5} y={10} width={2.5} height={2.5} rx={0.5} fill={detailColor} />
    <line x1={8.5} y1={15} x2={15.5} y2={15} stroke={detailColor} strokeWidth={1} strokeLinecap="round" />
    <line x1={8.5} y1={16.5} x2={15.5} y2={16.5} stroke={detailColor} strokeWidth={1} strokeLinecap="round" />
    <rect x={3.5} y={11} width={1.5} height={4} rx={0.5} fill={primaryColor} stroke={strokeColor} strokeWidth={0.5} />
    <rect x={19} y={11} width={1.5} height={4} rx={0.5} fill={primaryColor} stroke={strokeColor} strokeWidth={0.5} />
    <rect x={7} y={19} width={3} height={2.5} rx={0.5} fill={primaryColor} stroke={strokeColor} strokeWidth={0.5} />
    <rect x={14} y={19} width={3} height={2.5} rx={0.5} fill={primaryColor} stroke={strokeColor} strokeWidth={0.5} />
  </svg>
);

export const FlagIcon: React.FC<FlagIconProps> = ({
  className = 'w-5 h-5',
  color = '#FF7A45',
  strokeWidth = 1.8,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" className={className} {...props}>
    <path
      d="M6 4.5V21M6 4.5L6.2 4.4C8.8 3.3 11.6 5.7 14.2 4.6C15.3 4.1 16.4 4.2 17.5 4.7V14.1C16.4 13.6 15.3 13.5 14.2 14C11.6 15.1 8.8 12.7 6.2 13.8L6 13.9"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

interface QuestionMarkIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const ShareIcon: React.FC<SimpleIconProps> = ({ className = 'h-5 w-5', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 50 50"
    fill="currentColor"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path d="M25 5.5c.3 0 .6.1.8.3l7 6.5a1.2 1.2 0 01-1.6 1.7L26 9.4V25a1 1 0 11-2 0V9.4l-5.2 4.6a1.2 1.2 0 01-1.6-1.8l7-6.4c.2-.2.5-.3.8-.3z" />
    <path d="M33 18c2.8 0 5 2.2 5 5v13c0 2.8-2.2 5-5 5H17c-2.8 0-5-2.2-5-5V23c0-2.8 2.2-5 5-5h4.4a1 1 0 010 2H17a3 3 0 00-3 3v13a3 3 0 003 3h16a3 3 0 003-3V23a3 3 0 00-3-3h-4.4a1 1 0 110-2H33z" />
    <path d="M31.5 16.5a1 1 0 10-1.9-.6l-.3 1.1a1 1 0 001.9.6l.3-1.1zM19.5 16a1 1 0 11-1.9-.6l.3-1a1 1 0 011.9.6l-.3 1z" />
  </svg>
);

export const QuestionMarkIcon: React.FC<QuestionMarkIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#26A69A',
  accentColor = '#FF6F00',
  backgroundOpacity = 0.15,
  ...props
}) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <circle cx={12} cy={12} r={10} fill={primaryColor} opacity={backgroundOpacity} />
    <circle cx={12} cy={12} r={10} stroke={primaryColor} strokeWidth={2} fill="none" />
    <path
      d="M10 8.5C10 7.12 11.12 6 12.5 6C13.88 6 15 7.12 15 8.5C15 9.6 14.3 10.5 13.3 10.9L12.5 11.2V13"
      stroke={accentColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx={12.5} cy={16} r={1.2} fill={accentColor} />
  </svg>
);

export const TrophyIcon: React.FC<TrophyIconProps> = ({
  className = 'h-5 w-5',
  variant = 'orange',
  primaryColor,
  accentColor,
  backgroundOpacity = 0.1,
  ...props
}) => {
  const colors =
    variant === 'teal'
      ? { primary: '#26A69A', accent: '#FF6F00' }
      : { primary: '#FF6F00', accent: '#26A69A' };

  const resolvedPrimary = primaryColor ?? colors.primary;
  const resolvedAccent = accentColor ?? colors.accent;

  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
      <circle cx={16} cy={16} r={15} fill={resolvedPrimary} opacity={backgroundOpacity} />
      <path
        d="M10 12C10 10.8954 10.8954 10 12 10H20C21.1046 10 22 10.8954 22 12V14C22 16.2091 20.2091 18 18 18H14C11.7909 18 10 16.2091 10 14V12Z"
        fill={resolvedPrimary}
      />
      <rect x={14} y={18} width={4} height={3} fill={resolvedPrimary} />
      <rect x={11} y={21} width={10} height={2} rx={1} fill={resolvedPrimary} />
      <circle cx={16} cy={13} r={1.5} fill={resolvedAccent} opacity={0.8} />
    </svg>
  );
};

interface ReviewIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  detailColor?: string;
  backgroundOpacity?: number;
}

export const ReviewIcon: React.FC<ReviewIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#0B2137',
  accentColor = '#26A69A',
  detailColor = '#FFF6EE',
  backgroundOpacity = 0.1,
  ...props
}) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...props}>
    <circle cx={16} cy={16} r={15} fill={primaryColor} opacity={backgroundOpacity} />
    <path d="M16 11C10 11 6 16 6 16C6 16 10 21 16 21C22 21 26 16 26 16C26 16 22 11 16 11Z" fill={primaryColor} />
    <circle cx={16} cy={16} r={3.5} fill={accentColor} />
    <circle cx={16} cy={16} r={1.5} fill={primaryColor} />
    <circle cx={17} cy={15} r={0.8} fill={detailColor} />
  </svg>
);

interface ThumbIconProps extends SimpleIconProps {
  primaryColor?: string;
  accentColor?: string;
  backgroundOpacity?: number;
}

export const ThumbsUpIcon: React.FC<ThumbIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#10B4A4',
  accentColor = '#0B2137',
  backgroundOpacity = 0.12,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <circle cx={12} cy={12} r={11} fill={primaryColor} opacity={backgroundOpacity} />
    <path
      d="M12.25 5.5L11 10.5H7.8c-.9 0-1.7.6-1.9 1.5l-1.2 5c-.3 1.2.6 2.3 1.8 2.3H15c.9 0 1.7-.6 1.9-1.5l1.8-6a2 2 0 00-1.9-2.5h-3.1l.5-2.7a1.7 1.7 0 00-1.6-2.1H11c-.35 0-.66.23-.75.55Z"
      fill={primaryColor}
      stroke={accentColor}
      strokeWidth={1.4}
      strokeLinejoin="round"
    />
    <rect
      x={4.5}
      y={10}
      width={2.6}
      height={9}
      rx={1.2}
      fill={accentColor}
      opacity={0.9}
    />
  </svg>
);

export const ThumbsDownIcon: React.FC<ThumbIconProps> = ({
  className = 'h-5 w-5',
  primaryColor = '#FF9A3D',
  accentColor = '#0B2137',
  backgroundOpacity = 0.12,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <circle cx={12} cy={12} r={11} fill={primaryColor} opacity={backgroundOpacity} />
    <g transform="translate(24 24) rotate(180)">
      <path
        d="M12.25 5.5L11 10.5H7.8c-.9 0-1.7.6-1.9 1.5l-1.2 5c-.3 1.2.6 2.3 1.8 2.3H15c.9 0 1.7-.6 1.9-1.5l1.8-6a2 2 0 00-1.9-2.5h-3.1l.5-2.7a1.7 1.7 0 00-1.6-2.1H11c-.35 0-.66.23-.75.55Z"
        fill={primaryColor}
        stroke={accentColor}
        strokeWidth={1.4}
        strokeLinejoin="round"
      />
      <rect
        x={4.5}
        y={10}
        width={2.6}
        height={9}
        rx={1.2}
        fill={accentColor}
        opacity={0.9}
      />
    </g>
  </svg>
);
