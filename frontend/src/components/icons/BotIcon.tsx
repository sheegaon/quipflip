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
      {/* Main robot body - more square */}
      <rect x="5" y="6" width="14" height="13" rx="2" fill="#FF9A3D" stroke="#E26A00" strokeWidth="1" />

      {/* Antenna - shorter */}
      <line x1="12" y1="3.5" x2="12" y2="6" stroke="#FF9A3D" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="12" cy="2.5" r="1.2" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />

      {/* Eyes - larger and more square */}
      <rect x="8" y="10" width="2.5" height="2.5" rx="0.5" fill="#0B2137" />
      <rect x="13.5" y="10" width="2.5" height="2.5" rx="0.5" fill="#0B2137" />

      {/* Mouth/speaker grille */}
      <line x1="8.5" y1="15" x2="15.5" y2="15" stroke="#0B2137" strokeWidth="1" strokeLinecap="round" />
      <line x1="8.5" y1="16.5" x2="15.5" y2="16.5" stroke="#0B2137" strokeWidth="1" strokeLinecap="round" />

      {/* Side panels/arms - integrated into body */}
      <rect x="3.5" y="11" width="1.5" height="4" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
      <rect x="19" y="11" width="1.5" height="4" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />

      {/* Bottom base/feet - wider and more stable */}
      <rect x="7" y="19" width="3" height="2.5" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
      <rect x="14" y="19" width="3" height="2.5" rx="0.5" fill="#FF9A3D" stroke="#E26A00" strokeWidth="0.5" />
    </svg>
  );
};
