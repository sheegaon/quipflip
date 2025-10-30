import React from 'react';

type ThumbFeedbackButtonProps = {
  type: 'like' | 'dislike';
  isActive: boolean;
  onClick: () => void;
  disabled?: boolean;
};

const ThumbSvg: React.FC<{ direction: 'up' | 'down' }> = ({ direction }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`w-4 h-4 md:w-5 md:h-5 ${direction === 'down' ? 'rotate-180' : ''}`}
  >
    <path
      d="M6 11.5H4.75C3.784 11.5 3 12.284 3 13.25V19.5C3 20.328 3.672 21 4.5 21H6C6.828 21 7.5 20.328 7.5 19.5V13.25C7.5 12.284 6.716 11.5 5.75 11.5H6Z"
      fill="currentColor"
    />
    <path
      d="M8.75 11.5H16.5C18.433 11.5 20 13.067 20 15V16.114C20 16.408 19.959 16.701 19.878 16.984L18.86 20.553C18.482 21.867 17.3 22.75 15.933 22.75H10.5C9.25736 22.75 8.25 21.7426 8.25 20.5V12C8.25 11.724 8.474 11.5 8.75 11.5Z"
      fill="currentColor"
    />
    <path
      d="M8.5 11.5L10.839 5.014C11.255 3.918 12.305 3.191 13.479 3.25L14.165 3.284C15.673 3.36 16.85 4.635 16.85 6.144V9.5H19C20.657 9.5 22 10.843 22 12.5V13.011C22 13.333 21.95 13.652 21.853 13.958L20.838 17.164"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
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
