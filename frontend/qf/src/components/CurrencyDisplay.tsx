import React from 'react';
import {
  CurrencyDisplay as SharedCurrencyDisplay,
  type CurrencyDisplayProps as SharedCurrencyDisplayProps,
} from '@crowdcraft/components/CurrencyDisplay.tsx';

export type CurrencyDisplayProps = SharedCurrencyDisplayProps;

export const CurrencyDisplay: React.FC<CurrencyDisplayProps> = (props) => (
  <SharedCurrencyDisplay iconAlt="FlipCoins" {...props} />
);

export default CurrencyDisplay;
