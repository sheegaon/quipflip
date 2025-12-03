/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import { createNotificationContext } from '@crowdcraft/contexts/NotificationContext';
import type { NotificationMessage, PingToastMessage } from '@crowdcraft/contexts/NotificationContext';
import { useGame } from './GameContext';
import { notificationConfig } from '../config/contexts/notificationConfig';

const { NotificationProvider: SharedNotificationProvider, useNotifications } = createNotificationContext();

export { useNotifications };
export type { NotificationMessage, PingToastMessage };

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();

  return (
    <SharedNotificationProvider
      config={notificationConfig}
      isAuthenticated={state.isAuthenticated}
    >
      {children}
    </SharedNotificationProvider>
  );
};
