import React from 'react';

interface TreasureChestIconProps {
  className?: string;
  isAvailable?: boolean;
}

export const TreasureChestIcon: React.FC<TreasureChestIconProps> = ({
  className = '',
  isAvailable = false
}) => {
  const fillColor = isAvailable ? '#F97316' : '#94A3B8'; // quip-orange or gray
  const accentColor = isAvailable ? '#EA580C' : '#64748B'; // quip-orange-deep or darker gray

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      className={className}
      fill="none"
    >
      {/* Chest body */}
      <rect
        x="8"
        y="28"
        width="48"
        height="28"
        rx="2"
        fill={fillColor}
        stroke={accentColor}
        strokeWidth="2"
      />

      {/* Chest lid */}
      <path
        d="M 8 28 Q 8 14, 32 14 Q 56 14, 56 28 L 56 32 L 8 32 Z"
        fill={fillColor}
        stroke={accentColor}
        strokeWidth="2"
      />

      {/* Lock */}
      <circle
        cx="32"
        cy="36"
        r="4"
        fill={accentColor}
      />
      <rect
        x="30"
        y="36"
        width="4"
        height="8"
        rx="1"
        fill={accentColor}
      />

      {/* Decorative bands */}
      <line
        x1="8"
        y1="36"
        x2="56"
        y2="36"
        stroke={accentColor}
        strokeWidth="1.5"
      />
      <line
        x1="8"
        y1="48"
        x2="56"
        y2="48"
        stroke={accentColor}
        strokeWidth="1.5"
      />

      {/* Side reinforcements */}
      <rect
        x="12"
        y="28"
        width="3"
        height="28"
        fill={accentColor}
        opacity="0.6"
      />
      <rect
        x="49"
        y="28"
        width="3"
        height="28"
        fill={accentColor}
        opacity="0.6"
      />

      {/* Sparkles when available */}
      {isAvailable && (
        <>
          <circle cx="16" cy="20" r="1.5" fill="#FCD34D" opacity="0.8">
            <animate
              attributeName="opacity"
              values="0.8;0.3;0.8"
              dur="1.5s"
              repeatCount="indefinite"
            />
          </circle>
          <circle cx="48" cy="22" r="1.5" fill="#FCD34D" opacity="0.8">
            <animate
              attributeName="opacity"
              values="0.3;0.8;0.3"
              dur="1.5s"
              repeatCount="indefinite"
            />
          </circle>
          <circle cx="32" cy="10" r="2" fill="#FCD34D" opacity="0.8">
            <animate
              attributeName="opacity"
              values="0.5;1;0.5"
              dur="1.5s"
              repeatCount="indefinite"
            />
          </circle>
        </>
      )}
    </svg>
  );
};
