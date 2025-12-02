import { FC } from 'react';
import NotificationToast, { NotificationToastProps } from './NotificationToast';
import { NotificationMessage } from '../contexts/NotificationContext';

export interface NotificationDisplayProps {
  notifications: NotificationMessage[];
  onDismiss: (id: string) => void;
  maxVisible?: number;
  actionLabel?: NotificationToastProps['actionLabel'];
  onAction?: NotificationToastProps['onAction'];
}

const NotificationDisplay: FC<NotificationDisplayProps> = ({
  notifications,
  onDismiss,
  maxVisible = 3,
  actionLabel,
  onAction,
}) => {
  const visibleNotifications = notifications.slice(-maxVisible);

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {visibleNotifications.map((notification) => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onDismiss={() => onDismiss(notification.id)}
          actionLabel={actionLabel}
          onAction={onAction}
        />
      ))}
    </div>
  );
};

export default NotificationDisplay;
