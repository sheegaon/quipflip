import React from 'react';

interface StateIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

interface StateErrorIconProps extends StateIconProps {
  primaryColor?: string;
  accentColor?: string;
  warningColor?: string;
  detailColor?: string;
}

export const StateErrorIcon: React.FC<StateErrorIconProps> = ({
  className = 'w-16 h-16',
  primaryColor = '#10B5A4',
  accentColor = '#FFF7EA',
  warningColor = '#FFC857',
  detailColor = '#0E6F6A',
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <path d="M5 5h10a2 2 0 012 2v5H5a2 2 0 01-2-2V7a2 2 0 012-2z" fill={primaryColor} />
    <path
      d="M9 5l2 3-2 2 3 3"
      fill="none"
      stroke={accentColor}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M12.5 12l4.5 8h-9z" fill={warningColor} />
    <rect x={12} y={14.5} width={1} height={3.8} rx={0.5} fill={detailColor} />
    <rect x={12} y={19.2} width={1} height={1} rx={0.5} fill={detailColor} />
  </svg>
);

interface StateLoadingIconProps extends StateIconProps {
  primaryColor?: string;
  accentColor?: string;
  ringOpacity?: number;
}

export const StateLoadingIcon: React.FC<StateLoadingIconProps> = ({
  className = 'w-14 h-14',
  primaryColor = '#10B5A4',
  accentColor = '#FFC857',
  ringOpacity = 0.25,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <circle cx={12} cy={12} r={8} fill="none" stroke={primaryColor} strokeWidth={4} opacity={ringOpacity} />
    <path d="M12 4a8 8 0 11-6.93 4" fill="none" stroke={primaryColor} strokeWidth={4} strokeLinecap="round" />
    <circle cx={5.07} cy={8} r={2} fill={accentColor} />
  </svg>
);

interface StateEmptyIconProps extends StateIconProps {
  primaryColor?: string;
  secondaryColor?: string;
  detailColor?: string;
  accentColor?: string;
  accentOpacity?: number;
}

export const StateEmptyIcon: React.FC<StateEmptyIconProps> = ({
  className = 'w-20 h-20',
  primaryColor = '#0E6F6A',
  secondaryColor = '#10B5A4',
  detailColor = '#FFF7EA',
  accentColor = '#FFC857',
  accentOpacity = 0.85,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <rect x={3} y={14} width={18} height={6} rx={2} fill={primaryColor} />
    <rect x={6} y={15} width={12} height={3} rx={1.5} fill={detailColor} opacity={accentOpacity} />
    <rect x={6} y={4} width={12} height={8} rx={2} fill={secondaryColor} opacity={0.35} />
    <path d="M18.5 6.5l.7 1.3 1.3.7-1.3.7-.7 1.3-.7-1.3-1.3-.7 1.3-.7z" fill={accentColor} />
  </svg>
);

interface StateFilterEmptyIconProps extends StateIconProps {
  primaryColor?: string;
  secondaryColor?: string;
  accentColor?: string;
}

export const StateFilterEmptyIcon: React.FC<StateFilterEmptyIconProps> = ({
  className = 'w-16 h-16',
  primaryColor = '#10B5A4',
  secondaryColor = '#FFF7EA',
  accentColor = '#0E6F6A',
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <path d="M4 5h16l-6 6v4.5c0 .4-.2.8-.5 1l-3 2V11L4 5z" fill={primaryColor} />
    <circle cx={18} cy={18} r={4} fill={secondaryColor} />
    <path d="M16.6 16.6l2.8 2.8M19.4 16.6l-2.8 2.8" stroke={accentColor} strokeWidth={2} strokeLinecap="round" />
  </svg>
);
