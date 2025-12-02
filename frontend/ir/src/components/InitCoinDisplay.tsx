import React from 'react';

interface InitCoinDisplayProps {
  amount: number;
  className?: string;
  iconClassName?: string;
  textClassName?: string;
}

const InitCoinDisplay: React.FC<InitCoinDisplayProps> = ({
  amount,
  className = '',
  iconClassName = 'w-4 h-4',
  textClassName = 'text-sm font-semibold',
}) => {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <img
        src="/wallet.png"
        alt="IC"
        className={iconClassName}
      />
      <span className={textClassName}>{amount.toLocaleString()}</span>
    </span>
  );
};

export default InitCoinDisplay;
