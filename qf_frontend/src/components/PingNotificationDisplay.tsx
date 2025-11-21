import React from 'react';
import { useNotifications } from '../contexts/NotificationContext';
import { SuccessNotification } from './SuccessNotification';

export const PingNotificationDisplay: React.FC = () => {
  const { pingMessages, removePingMessage } = useNotifications();
  const activePing = pingMessages[0];

  if (!activePing) {
    return null;
  }

  return (
    <SuccessNotification
      message={activePing.message}
      onDismiss={() => removePingMessage(activePing.id)}
      icon="📣"
    />
  );
};

export default PingNotificationDisplay;
