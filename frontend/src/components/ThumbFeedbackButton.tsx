import React from 'react';

type ThumbFeedbackButtonProps = {
  type: 'like' | 'dislike';
  isActive: boolean;
  onClick: () => void;
  disabled?: boolean;
};

const ThumbSvg: React.FC<{ direction: 'up' | 'down' }> = ({ direction }) => (
  <svg
    viewBox="0 0 20 24"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
    className={`w-5 h-5 md:w-6 md:h-6 ${direction === 'down' ? 'rotate-180' : ''}`}
  >
    {/* Rounded, emoji-style thumb - base section (wider) */}
    <path
      d="M5 10.5C5 9.67 5.67 9 6.5 9H8.5C9.33 9 10 9.67 10 10.5V19.5C10 20.33 9.33 21 8.5 21H6.5C5.67 21 5 20.33 5 19.5V10.5Z"
      fillOpacity="0.9"
    />
    {/* Main thumb section (wider) */}
    <path
      d="M10.5 11H15.5C16.6 11 17.5 11.9 17.5 13V14.5C17.5 14.8 17.45 15.1 17.35 15.4L16.2 18.9C15.9 19.8 15.1 20.5 14.1 20.5H11.5C10.95 20.5 10.5 20.05 10.5 19.5V11Z"
      fillOpacity="0.9"
    />
    {/* Extended thumb gesture (wider) */}
    <path
      d="M10 11V6C10 4.62 11.12 3.5 12.5 3.5C12.78 3.5 13 3.72 13 4V7.5C13 8.33 13.67 9 14.5 9H16C16.55 9 17 9.45 17 10C17 10.28 16.89 10.54 16.71 10.71L11.71 15.71C11.29 16.13 10.5 15.83 10.5 15.26V11.5C10.5 11.22 10.28 11 10 11Z"
      fillOpacity="0.95"
    />
  </svg>
);

export const ThumbFeedbackButton: React.FC<ThumbFeedbackButtonProps> = ({
  type,
  isActive,
  onClick,
  disabled = false,
}) => {
  const isLike = type === 'like';
  const activeBackground = isLike ? 'bg-quip-turquoise text-white shadow-tile-sm' : 'bg-quip-orange text-quip-navy shadow-tile-sm';
  const inactiveStyles = isLike
    ? 'text-quip-turquoise/80 border-quip-turquoise/30 hover:text-quip-turquoise hover:border-quip-turquoise/60 hover:bg-quip-turquoise/10'
    : 'text-quip-orange/80 border-quip-orange/30 hover:text-quip-orange hover:border-quip-orange/60 hover:bg-quip-orange/10';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={isActive}
      className={`relative inline-flex h-9 w-9 md:h-11 md:w-11 items-center justify-center rounded-full border-2 transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-quip-cream ${
        isActive ? activeBackground : `bg-white/90 ${inactiveStyles}`
      } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
      title={isLike ? 'I like this prompt' : 'I dislike this prompt'}
      aria-label={isLike ? 'Like this prompt' : 'Dislike this prompt'}
    >
      <ThumbSvg direction={isLike ? 'up' : 'down'} />
      <span
        className={`pointer-events-none absolute inset-0 rounded-full bg-gradient-to-br opacity-0 transition-opacity duration-200 ${
          isActive ? 'from-white/30 via-white/10 to-transparent opacity-60' : ''
        }`}
        aria-hidden="true"
      />
    </button>
  );
};

export default ThumbFeedbackButton;
