/**
 * Notification Display Component
 *
 * Renders notification toasts consumed from NotificationContext.
 * Displays at bottom-right, stacking up to 3 notifications.
 * Auto-dismisses after 5 seconds.
 *
 * Uses SuccessNotification styling for consistency.
 */

import { FC } from 'react';
import { useNotifications } from '../contexts/NotificationContext';
import NotificationToast from './NotificationToast';

const NotificationDisplay: FC = () => {
  const { notifications, removeNotification } = useNotifications();

  // Only show last 3 notifications
  const visibleNotifications = notifications.slice(-3);

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {visibleNotifications.map((notification) => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onDismiss={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  );
};

export default NotificationDisplay;
