import React from 'react';
import { EyeIcon } from '../icons/EyeIcon';

interface ReviewBackButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export const ReviewBackButton: React.FC<ReviewBackButtonProps> = ({ onClick, disabled = false }) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
      title="Back to Completed Rounds"
    >
      <EyeIcon />
      <span>Back to Completed Rounds</span>
    </button>
  );
};
