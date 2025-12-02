import React from 'react';
import { PingToastMessage } from '../contexts/NotificationContext';
import { SuccessNotification } from './SuccessNotification';

export interface PingNotificationDisplayProps {
  pingMessage?: PingToastMessage;
  onDismiss: (id: string) => void;
  onAction?: (joinUrl: string) => void;
  actionLabel?: string;
}

export const PingNotificationDisplay: React.FC<PingNotificationDisplayProps> = ({
  pingMessage,
  onDismiss,
  onAction,
  actionLabel = 'Return to party',
}) => {
  if (!pingMessage) {
    return null;
  }

  return (
    <SuccessNotification
      message={pingMessage.message}
      onDismiss={() => onDismiss(pingMessage.id)}
      icon="📣"
      actionLabel={pingMessage.joinUrl ? actionLabel : undefined}
      onAction={
        pingMessage.joinUrl && onAction
          ? () => onAction(pingMessage.joinUrl as string)
          : undefined
      }
    />
  );
};

export default PingNotificationDisplay;
