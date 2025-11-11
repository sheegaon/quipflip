import React from 'react';

interface BotIconProps {
  className?: string;
}

export const BotIcon: React.FC<BotIconProps> = ({ className = 'h-4 w-4' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-label="AI Player"
    >
      {/* Robot head */}
      <rect x="6" y="7" width="12" height="11" rx="2" fill="#FF9A3D" stroke="#E26A00" strokeWidth="1" />

      {/* Antenna */}
      <line x1="12" y1="4" x2="12" y2="7" stroke="#FF9A3D" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="12" cy="3" r="1.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />

      {/* Eyes */}
      <circle cx="9.5" cy="11" r="1.5" fill="#0B2137" />
      <circle cx="14.5" cy="11" r="1.5" fill="#0B2137" />

      {/* Mouth/speaker grille - three horizontal lines */}
      <line x1="9" y1="14.5" x2="15" y2="14.5" stroke="#0B2137" strokeWidth="1" strokeLinecap="round" />
      <line x1="9" y1="16" x2="15" y2="16" stroke="#0B2137" strokeWidth="1" strokeLinecap="round" />

      {/* Arms */}
      <rect x="4" y="10" width="2" height="4" rx="1" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
      <rect x="18" y="10" width="2" height="4" rx="1" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />

      {/* Legs */}
      <rect x="8" y="18" width="2" height="3" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
      <rect x="14" y="18" width="2" height="3" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
    </svg>
  );
};
