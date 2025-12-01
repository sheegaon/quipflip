import React, { useId } from 'react';

interface TreasureChestIconProps {
  className?: string;
  isAvailable?: boolean;
}

export const TreasureChestIcon: React.FC<TreasureChestIconProps> = ({
  className = '',
  isAvailable = false,
}) => {
  const uniqueId = useId().replace(/:/g, '_');
  const bodyGradientId = `${uniqueId}_body`;
  const lidGradientId = `${uniqueId}_lid`;
  const metalGradientId = `${uniqueId}_metal`;
  const lockGradientId = `${uniqueId}_lock`;

  const woodHighlight = isAvailable ? '#FBBF24' : '#E2E8F0';
  const woodShadow = isAvailable ? '#92400E' : '#64748B';
  const woodMid = isAvailable ? '#D97706' : '#94A3B8';
  const metalLight = isAvailable ? '#FDE68A' : '#D1D5DB';
  const metalShadow = isAvailable ? '#B45309' : '#6B7280';
  const outline = isAvailable ? '#78350F' : '#4B5563';
  const coinGlow = isAvailable ? '#FDE68A' : '#E2E8F0';

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      className={className}
      fill="none"
    >
      <defs>
        <linearGradient id={bodyGradientId} x1="12" y1="30" x2="12" y2="58">
          <stop offset="0" stopColor={woodHighlight} />
          <stop offset="0.45" stopColor={woodMid} />
          <stop offset="1" stopColor={woodShadow} />
        </linearGradient>
        <linearGradient id={lidGradientId} x1="32" y1="12" x2="32" y2="32">
          <stop offset="0" stopColor={woodHighlight} />
          <stop offset="0.75" stopColor={woodMid} />
          <stop offset="1" stopColor={woodShadow} />
        </linearGradient>
        <linearGradient id={metalGradientId} x1="32" y1="34" x2="32" y2="42">
          <stop offset="0" stopColor={metalLight} />
          <stop offset="1" stopColor={metalShadow} />
        </linearGradient>
        <linearGradient id={lockGradientId} x1="32" y1="40" x2="32" y2="52">
          <stop offset="0" stopColor={metalLight} />
          <stop offset="1" stopColor={metalShadow} />
        </linearGradient>
      </defs>

      {/* Chest lid */}
      <path
        d="M12 30V24C12 16 20 10 32 10C44 10 52 16 52 24V30Z"
        fill={`url(#${lidGradientId})`}
        stroke={outline}
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* Lid highlight */}
      <path
        d="M16 26C16 20.5 22 16 32 16C42 16 48 20.5 48 26"
        stroke={metalLight}
        strokeOpacity="0.3"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Coins peeking out when available */}
      {isAvailable && (
        <path
          d="M18 28C18 26 22 24 32 24C42 24 46 26 46 28"
          stroke={coinGlow}
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.8"
        />
      )}

      {/* Chest body */}
      <path
        d="M12 30H52C55.3137 30 58 32.6863 58 36V50C58 55.5228 53.5228 60 48 60H16C10.4772 60 6 55.5228 6 50V36C6 32.6863 8.68629 30 12 30Z"
        fill={`url(#${bodyGradientId})`}
        stroke={outline}
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* Wood planks */}
      <path
        d="M20 32V56M32 32V56M44 32V56"
        stroke={outline}
        strokeOpacity="0.35"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Metal band */}
      <path
        d="M8 40H56"
        stroke={outline}
        strokeWidth="5"
        strokeLinecap="round"
        opacity="0.65"
      />
      <rect
        x="10"
        y="36"
        width="44"
        height="8"
        rx="2"
        fill={`url(#${metalGradientId})`}
        opacity="0.95"
      />

      {/* Lock plate */}
      <rect
        x="27"
        y="37"
        width="10"
        height="14"
        rx="2"
        fill={`url(#${lockGradientId})`}
        stroke={outline}
        strokeWidth="1.5"
      />
      <path
        d="M32 42C33.1046 42 34 42.8954 34 44C34 44.8284 33.5 45.5 32.85 45.8284V48.5C32.85 49.3284 32.1784 50 31.35 50H30.65C29.8216 50 29.15 49.3284 29.15 48.5V45.8284C28.5 45.5 28 44.8284 28 44C28 42.8954 28.8954 42 30 42Z"
        fill={outline}
        opacity="0.85"
      />

      {/* Base shadow */}
      <ellipse cx="32" cy="60" rx="18" ry="2.5" fill={outline} opacity="0.2" />

      {/* Sparkles when available */}
      {isAvailable && (
        <>
          <path
            d="M14 18L15.5 21.5L19 23L15.5 24.5L14 28L12.5 24.5L9 23L12.5 21.5Z"
            fill={coinGlow}
            opacity="0.85"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              values="-5 14 23;5 14 23;-5 14 23"
              dur="2s"
              repeatCount="indefinite"
            />
          </path>
          <path
            d="M50 18L51 20.5L53.5 21.5L51 22.5L50 25L49 22.5L46.5 21.5L49 20.5Z"
            fill={coinGlow}
            opacity="0.75"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              values="0 50 21;10 50 21;0 50 21"
              dur="1.8s"
              repeatCount="indefinite"
            />
          </path>
          <circle cx="32" cy="12" r="3" fill={coinGlow} opacity="0.8">
            <animate
              attributeName="opacity"
              values="0.6;1;0.6"
              dur="1.6s"
              repeatCount="indefinite"
            />
          </circle>
        </>
      )}
    </svg>
  );
};
