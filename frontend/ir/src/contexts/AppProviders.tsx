import React, { ReactNode } from 'react';
import { IRGameProvider } from './IRGameContext';
import { NavigationHistoryProvider } from './NavigationHistoryContext';
import { NetworkProvider } from './NetworkContext';
import { NotificationProvider } from './NotificationContext';
import { TutorialProvider } from './TutorialContext';

interface AppProvidersProps {
  children: ReactNode;
}

export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  return (
    <NetworkProvider>
      <TutorialProvider>
        <IRGameProvider>
          <NotificationProvider>
            <NavigationHistoryProvider>{children}</NavigationHistoryProvider>
          </NotificationProvider>
        </IRGameProvider>
      </TutorialProvider>
    </NetworkProvider>
  );
};
