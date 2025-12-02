import React from 'react';

interface CurrencyDisplayProps {
  amount: number;
  iconClassName?: string;
  textClassName?: string;
  showIcon?: boolean;
}

/**
 * Displays currency amounts with the flipcoin icon instead of $.
 * Provides consistent currency branding throughout the application.
 *
 * @param amount - The numeric currency value to display
 * @param iconClassName - Optional CSS classes for the icon (default: "w-4 h-4")
 * @param textClassName - Optional CSS classes for the text
 * @param showIcon - Whether to show the icon (default: true)
 */
export const CurrencyDisplay: React.FC<CurrencyDisplayProps> = ({
  amount,
  iconClassName = "w-4 h-4",
  textClassName = "",
  showIcon = true,
}) => {
  return (
    <span className="inline-flex items-center gap-1">
      {showIcon && (
        <img
          src="/wallet.png"
          alt="FlipCoins"
          className={iconClassName}
        />
      )}
      <span className={textClassName}>{amount}</span>
    </span>
  );
};

export default CurrencyDisplay;
