import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../contexts/NotificationContext';
import { SuccessNotification } from './SuccessNotification';

export const PingNotificationDisplay: React.FC = () => {
  const { pingMessages, removePingMessage } = useNotifications();
  const activePing = pingMessages[0];
  const navigate = useNavigate();

  if (!activePing) {
    return null;
  }

  return (
    <SuccessNotification
      message={activePing.message}
      onDismiss={() => removePingMessage(activePing.id)}
      icon="📣"
      actionLabel={activePing.joinUrl ? 'Return to party' : undefined}
      onAction={activePing.joinUrl ? () => navigate(activePing.joinUrl!) : undefined}
    />
  );
};

export default PingNotificationDisplay;
