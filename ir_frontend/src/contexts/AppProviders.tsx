import React, { ReactNode } from 'react';
import { IRGameProvider } from './IRGameContext';
import { NotificationProvider } from './NotificationContext';
import { TutorialProvider } from './TutorialContext';

interface AppProvidersProps {
  children: ReactNode;
}

export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  return (
    <TutorialProvider>
      <IRGameProvider>
        <NotificationProvider>{children}</NotificationProvider>
      </IRGameProvider>
    </TutorialProvider>
  );
};
