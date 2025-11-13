import React from 'react';

interface IconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

export const QuestOverviewIcon: React.FC<IconProps> = ({ className = 'w-8 h-8', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <rect x={3} y={3} width={18} height={18} rx={3} fill="#10B5A4" />
    <rect x={6} y={6} width={12} height={12} rx={2} fill="#FFF7EA" />
    <path d="M8 10l2 2 4-4" stroke="#FFC857" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    <rect x={8} y={14} width={8} height={2} rx={1} fill="#0E6F6A" />
  </svg>
);

export const QuestQualityIcon: React.FC<IconProps> = ({ className = 'w-8 h-8', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <path
      d="M12 3l2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9 6.8 19l1-5.8-4.2-4.1 5.8-.8z"
      fill="#10B5A4"
    />
    <path
      d="M12 6.2l1.8 3.7 4.1.6-3 2.9.7 4.1-3.6-1.9-3.6 1.9.7-4.1-3-2.9 4.1-.6z"
      fill="#FFF7EA"
    />
    <rect x={6} y={18.5} width={12} height={2.5} rx={1.2} fill="#FFC857" />
  </svg>
);

export const QuestActivityIcon: React.FC<IconProps> = ({ className = 'w-8 h-8', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <rect x={3} y={3} width={18} height={18} rx={4} fill="#FFF7EA" />
    <path
      d="M4 15h3l3-6 4 8 3-6h4"
      stroke="#0E6F6A"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx={19} cy={7} r={2} fill="#FFC857" />
  </svg>
);

export const QuestMilestoneIcon: React.FC<IconProps> = ({ className = 'w-8 h-8', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <rect x={3} y={20} width={18} height={2} rx={1} fill="#FFC857" />
    <rect x={6} y={4} width={2} height={16} rx={1} fill="#0E6F6A" />
    <path d="M8 5H16a2 2 0 010 4H8Z" fill="#10B5A4" />
  </svg>
);

export const QuestStreakIcon: React.FC<IconProps> = ({ className = 'w-8 h-8', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <path
      d="M12 3c2.2 2.1 3.2 3.8 3.2 6.1 0 1.9-1.2 3.4-3.2 3.4-2.1 0-3.2 1.4-3.2 3.2 0 2.3 1.9 4.3 4.8 4.3 3.7 0 6.4-2.8 6.4-6.5S17.3 8.2 15.6 6.6"
      fill="#FFC857"
    />
    <path
      d="M12 21c-2.4 0-4-1.6-4-3.5 0-1.6 1.2-2.9 3.3-3.1 2.1-.2 3.7-1.8 3.7-3.8 0-.9-.2-1.7-.7-2.6 2.2 1.5 3.7 3.6 3.7 6.1 0 3.4-2.6 6.9-6 6.9z"
      fill="#10B5A4"
      opacity={0.25}
    />
  </svg>
);

export const QuestClaimableIcon: React.FC<IconProps> = ({ className = 'w-7 h-7', ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    {...props}
  >
    <circle cx={16.5} cy={7.5} r={4.5} fill="#FFC857" />
    <path
      d="M14.7 7.6l1.6 1.6 3-3"
      stroke="#0E6F6A"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <rect x={3} y={12} width={12} height={8} rx={2} fill="#10B5A4" />
    <rect x={5} y={10} width={6} height={2} rx={1} fill="#0E6F6A" />
  </svg>
);
