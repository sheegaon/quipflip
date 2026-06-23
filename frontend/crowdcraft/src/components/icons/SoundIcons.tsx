import React from 'react';

interface SoundIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/** Speaker with sound waves — sounds are on. */
export const SoundOnIcon: React.FC<SoundIconProps> = ({ className = 'h-5 w-5', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path d="M11 5 6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none" />
    <path d="M15.5 8.5a5 5 0 0 1 0 7" />
    <path d="M18.5 6a9 9 0 0 1 0 12" />
  </svg>
);

/** Speaker with a slash — sounds are muted. */
export const SoundOffIcon: React.FC<SoundIconProps> = ({ className = 'h-5 w-5', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path d="M11 5 6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none" />
    <line x1={22} y1={9} x2={16} y2={15} />
    <line x1={16} y1={9} x2={22} y2={15} />
  </svg>
);

/** Bell — used for the host ping affordance. */
export const BellIcon: React.FC<SoundIconProps> = ({ className = 'h-5 w-5', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);
