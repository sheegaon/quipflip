import React from 'react';

interface SimpleIconProps {
  className?: string;
}

interface FlagIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
  color?: string;
  strokeWidth?: number | string;
}

interface ResultsIconProps extends SimpleIconProps {
  variant?: 'orange' | 'teal';
}

export const BotIcon: React.FC<SimpleIconProps> = ({ className = 'h-4 w-4' }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-label="AI Player">
    <rect x={5} y={6} width={14} height={13} rx={2} fill="#FF9A3D" stroke="#E26A00" strokeWidth={1} />
    <line x1={12} y1={3.5} x2={12} y2={6} stroke="#FF9A3D" strokeWidth={1.5} strokeLinecap="round" />
    <circle cx={12} cy={2.5} r={1.2} fill="#FF9A3D" stroke="#E26A00" strokeWidth={0.5} />
    <rect x={8} y={10} width={2.5} height={2.5} rx={0.5} fill="#0B2137" />
    <rect x={13.5} y={10} width={2.5} height={2.5} rx={0.5} fill="#0B2137" />
    <line x1={8.5} y1={15} x2={15.5} y2={15} stroke="#0B2137" strokeWidth={1} strokeLinecap="round" />
    <line x1={8.5} y1={16.5} x2={15.5} y2={16.5} stroke="#0B2137" strokeWidth={1} strokeLinecap="round" />
    <rect x={3.5} y={11} width={1.5} height={4} rx={0.5} fill="#FF9A3D" stroke="#E26A00" strokeWidth={0.5} />
    <rect x={19} y={11} width={1.5} height={4} rx={0.5} fill="#FF9A3D" stroke="#E26A00" strokeWidth={0.5} />
    <rect x={7} y={19} width={3} height={2.5} rx={0.5} fill="#FF9A3D" stroke="#E26A00" strokeWidth={0.5} />
    <rect x={14} y={19} width={3} height={2.5} rx={0.5} fill="#FF9A3D" stroke="#E26A00" strokeWidth={0.5} />
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

export const QuestionMarkIcon: React.FC<SimpleIconProps> = ({ className = 'h-5 w-5' }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx={12} cy={12} r={10} fill="#26A69A" opacity={0.15} />
    <circle cx={12} cy={12} r={10} stroke="#26A69A" strokeWidth={2} fill="none" />
    <path
      d="M10 8.5C10 7.12 11.12 6 12.5 6C13.88 6 15 7.12 15 8.5C15 9.6 14.3 10.5 13.3 10.9L12.5 11.2V13"
      stroke="#FF6F00"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx={12.5} cy={16} r={1.2} fill="#FF6F00" />
  </svg>
);

export const ResultsIcon: React.FC<ResultsIconProps> = ({ className = 'h-5 w-5', variant = 'orange' }) => {
  const colors =
    variant === 'teal'
      ? { primary: '#26A69A', accent: '#FF6F00' }
      : { primary: '#FF6F00', accent: '#26A69A' };

  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx={16} cy={16} r={15} fill={colors.primary} opacity={0.1} />
      <path
        d="M10 12C10 10.8954 10.8954 10 12 10H20C21.1046 10 22 10.8954 22 12V14C22 16.2091 20.2091 18 18 18H14C11.7909 18 10 16.2091 10 14V12Z"
        fill={colors.primary}
      />
      <rect x={14} y={18} width={4} height={3} fill={colors.primary} />
      <rect x={11} y={21} width={10} height={2} rx={1} fill={colors.primary} />
      <circle cx={16} cy={13} r={1.5} fill={colors.accent} opacity={0.8} />
    </svg>
  );
};

export const ReviewIcon: React.FC<SimpleIconProps> = ({ className = 'h-5 w-5' }) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <circle cx={16} cy={16} r={15} fill="#0B2137" opacity={0.1} />
    <path d="M16 11C10 11 6 16 6 16C6 16 10 21 16 21C22 21 26 16 26 16C26 16 22 11 16 11Z" fill="#0B2137" />
    <circle cx={16} cy={16} r={3.5} fill="#26A69A" />
    <circle cx={16} cy={16} r={1.5} fill="#0B2137" />
    <circle cx={17} cy={15} r={0.8} fill="#FFF6EE" />
  </svg>
);
