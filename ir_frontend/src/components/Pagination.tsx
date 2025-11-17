import React from 'react';
import { ArrowLeftIcon, ArrowRightIcon } from './icons/ArrowIcons';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
}) => {
  if (totalPages <= 1) {
    return null;
  }

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  const getButtonClassName = (disabled: boolean) => {
    return `p-2 rounded-full transition-all ${
      disabled
        ? 'opacity-30 cursor-not-allowed'
        : 'hover:bg-ir-turquoise hover:bg-opacity-10'
    }`;
  };

  return (
    <div className="flex items-center justify-center gap-4 py-4">
      <button
        onClick={handlePrevious}
        disabled={currentPage === 1}
        className={getButtonClassName(currentPage === 1)}
        aria-label="Previous page"
      >
        <ArrowLeftIcon className="w-4 h-6" aria-hidden="true" />
      </button>

      <div className="text-sm font-medium text-ir-navy">
        Page {currentPage} of {totalPages}
      </div>

      <button
        onClick={handleNext}
        disabled={currentPage === totalPages}
        className={getButtonClassName(currentPage === totalPages)}
        aria-label="Next page"
      >
        <ArrowRightIcon className="w-4 h-6" aria-hidden="true" />
      </button>
    </div>
  );
};
