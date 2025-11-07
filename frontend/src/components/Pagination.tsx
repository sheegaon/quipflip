import React from 'react';

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
        : 'hover:bg-quip-turquoise hover:bg-opacity-10'
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
        <img
          src="/icon_back_arrow.svg"
          alt="Previous"
          className="w-4 h-6"
        />
      </button>

      <div className="text-sm font-medium text-quip-navy">
        Page {currentPage} of {totalPages}
      </div>

      <button
        onClick={handleNext}
        disabled={currentPage === totalPages}
        className={getButtonClassName(currentPage === totalPages)}
        aria-label="Next page"
      >
        <img
          src="/icon_back_arrow.svg"
          alt="Next"
          className="w-4 h-6 transform rotate-180"
        />
      </button>
    </div>
  );
};
