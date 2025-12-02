import React from 'react';
import { useNavigate } from 'react-router-dom';
import PingNotificationDisplayBase from '@crowdcraft/components/PingNotificationDisplay.tsx';
import { useNotifications } from '../contexts/NotificationContext';

export const PingNotificationDisplay: React.FC = () => {
  const { pingMessages, removePingMessage } = useNotifications();
  const activePing = pingMessages[0];
  const navigate = useNavigate();

  return (
    <PingNotificationDisplayBase
      pingMessage={activePing}
      onDismiss={removePingMessage}
      onAction={(joinUrl) => navigate(joinUrl)}
      actionLabel={activePing?.joinUrl ? 'Return to party' : undefined}
    />
  );
};

export default PingNotificationDisplay;
