import React, { ReactNode } from 'react';
import { IRGameProvider } from './IRGameContext';

interface AppProvidersProps {
  children: ReactNode;
}

export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  return <IRGameProvider>{children}</IRGameProvider>;
};
