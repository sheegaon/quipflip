import React from 'react';

export interface CurrencyDisplayProps {
  amount: number;
  iconClassName?: string;
  textClassName?: string;
  showIcon?: boolean;
  iconAlt?: string;
  iconSrc?: string;
}

export const CurrencyDisplay: React.FC<CurrencyDisplayProps> = ({
  amount,
  iconClassName = 'w-4 h-4',
  textClassName = '',
  showIcon = true,
  iconAlt = 'Coins',
  iconSrc = '/wallet.png',
}) => {
  return (
    <span className="inline-flex items-center gap-1">
      {showIcon && (
        <img
          src={iconSrc}
          alt={iconAlt}
          className={iconClassName}
        />
      )}
      <span className={textClassName}>{amount}</span>
    </span>
  );
};

export default CurrencyDisplay;
