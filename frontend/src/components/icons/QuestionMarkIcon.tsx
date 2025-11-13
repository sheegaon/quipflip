import React from 'react';

interface QuestionMarkIconProps {
  className?: string;
}

export const QuestionMarkIcon: React.FC<QuestionMarkIconProps> = ({ className = 'h-5 w-5' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {/* Circle background */}
      <circle cx="12" cy="12" r="10" fill="#26A69A" opacity="0.15" />

      {/* Circle outline */}
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="#26A69A"
        strokeWidth="2"
        fill="none"
      />

      {/* Question mark - centered at x=12 */}
      {/* Top curve of question mark */}
      <path
        d="M10 8.5C10 7.12 11.12 6 12.5 6C13.88 6 15 7.12 15 8.5C15 9.6 14.3 10.5 13.3 10.9L12.5 11.2V13"
        stroke="#FF6F00"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Question mark dot */}
      <circle
        cx="12.5"
        cy="16"
        r="1.2"
        fill="#FF6F00"
      />
    </svg>
  );
};
