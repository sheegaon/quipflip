import React from "react";

type Props = { className?: string; size?: number };

export const TreasureIcon: React.FC<Props> = ({ className = "h-5 w-5", size = 24 }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    role="img"
    aria-label="Treasure"
  >
    <defs>
      {/* Fallbacks if CSS vars aren’t provided */}
      <style>{`
        :root {
          --q-teal-500: #10B5A4;
          --q-teal-700: #0E6F6A;
          --q-gold-500: #FFC857;
          --q-ivory-50: #FFF7EA;
          --q-ink-900: #0B2137;
        }
      `}</style>
    </defs>

    {/* Lid */}
    <rect x="3" y="5" width="18" height="5" rx="2"
      fill="var(--q-teal-500)" opacity="0.15"
      stroke="var(--q-teal-700)" strokeWidth="2" />

    {/* Chest body */}
    <rect x="3" y="8" width="18" height="11" rx="2"
      fill="var(--q-ivory-50)"
      stroke="var(--q-teal-700)" strokeWidth="2" />

    {/* Gold seam under lid */}
    <rect x="3" y="9" width="18" height="2" rx="1" fill="var(--q-gold-500)" />

    {/* Coins peeking */}
    <path d="M6.5 9.8c0-1 1-1.8 2.2-1.8s2.2.8 2.2 1.8M12.5 9.8c0-1 .9-1.8 2.1-1.8 1.2 0 2.1.8 2.1 1.8"
      fill="none" stroke="var(--q-gold-500)" strokeWidth="2" strokeLinecap="round" />

    {/* Center band */}
    <rect x="10.5" y="8" width="3" height="11" rx="1.5"
      fill="var(--q-teal-500)" opacity="0.18" />

    {/* Lock plate */}
    <rect x="10" y="12" width="4" height="5" rx="1"
      fill="var(--q-gold-500)" stroke="var(--q-teal-700)" strokeWidth="2" />
    <path d="M12 13.8v1.2" stroke="var(--q-ink-900)" strokeWidth="2" strokeLinecap="round" />
    <circle cx="12" cy="16" r="0.8" fill="var(--q-ink-900)" />

    {/* Tiny sparkle (optional accent) */}
    <path d="M18.3 6.3l.5 1 .9.5-.9.5-.5 1-.5-1-.9-.5.9-.5z" fill="var(--q-gold-500)" />
  </svg>
);
