import React from 'react';

interface StateIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

export const StateErrorIcon: React.FC<StateIconProps> = ({ className = 'w-16 h-16', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <path d="M5 5h10a2 2 0 012 2v5H5a2 2 0 01-2-2V7a2 2 0 012-2z" fill="#10B5A4" />
    <path
      d="M9 5l2 3-2 2 3 3"
      fill="none"
      stroke="#FFF7EA"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M12.5 12l4.5 8h-9z" fill="#FFC857" />
    <rect x={12} y={14.5} width={1} height={3.8} rx={0.5} fill="#0E6F6A" />
    <rect x={12} y={19.2} width={1} height={1} rx={0.5} fill="#0E6F6A" />
  </svg>
);

export const StateLoadingIcon: React.FC<StateIconProps> = ({ className = 'w-14 h-14', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <circle cx={12} cy={12} r={8} fill="none" stroke="#10B5A4" strokeWidth={4} opacity={0.25} />
    <path d="M12 4a8 8 0 11-6.93 4" fill="none" stroke="#10B5A4" strokeWidth={4} strokeLinecap="round" />
    <circle cx={5.07} cy={8} r={2} fill="#FFC857" />
  </svg>
);

export const StateEmptyIcon: React.FC<StateIconProps> = ({ className = 'w-20 h-20', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <rect x={3} y={14} width={18} height={6} rx={2} fill="#0E6F6A" />
    <rect x={6} y={15} width={12} height={3} rx={1.5} fill="#FFF7EA" opacity={0.85} />
    <rect x={6} y={4} width={12} height={8} rx={2} fill="#10B5A4" opacity={0.35} />
    <path d="M18.5 6.5l.7 1.3 1.3.7-1.3.7-.7 1.3-.7-1.3-1.3-.7 1.3-.7z" fill="#FFC857" />
  </svg>
);

export const StateFilterEmptyIcon: React.FC<StateIconProps> = ({ className = 'w-16 h-16', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    className={className}
    {...props}
  >
    <path d="M4 5h16l-6 6v4.5c0 .4-.2.8-.5 1l-3 2V11L4 5z" fill="#10B5A4" />
    <circle cx={18} cy={18} r={4} fill="#FFF7EA" />
    <path d="M16.6 16.6l2.8 2.8M19.4 16.6l-2.8 2.8" stroke="#0E6F6A" strokeWidth={2} strokeLinecap="round" />
  </svg>
);
