import React from 'react';
import { HomeIcon } from '../icons/NavigationIcons';

interface ReviewBackButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export const ReviewBackButton: React.FC<ReviewBackButtonProps> = ({ onClick, disabled = false }) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full mt-4 flex items-center justify-center gap-2 text-ccl-teal hover:text-ccl-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
      title="Dashboard"
    >
      <HomeIcon />
      <span>Dashboard</span>
    </button>
  );
};
