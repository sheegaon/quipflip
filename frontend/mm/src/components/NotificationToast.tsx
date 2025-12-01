/**
 * Notification Toast Component
 *
 * Individual toast notification with message and action button.
 * Slides in from right, auto-dismisses after 5 seconds.
 * Uses SuccessNotification styling and animation patterns.
 */

import { FC, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { NotificationMessage } from '../contexts/NotificationContext';
import { TrackingIcon } from './icons/NavigationIcons';

interface NotificationToastProps {
  notification: NotificationMessage;
  onDismiss: () => void;
}

const NotificationToast: FC<NotificationToastProps> = ({
  notification,
  onDismiss,
}) => {
  const [isExiting, setIsExiting] = useState(false);
  const navigate = useNavigate();

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      // Wait for exit animation to complete before calling onDismiss
      setTimeout(onDismiss, 300);
    }, 5000);

    return () => clearTimeout(timer);
  }, [onDismiss]);

  const handleManualDismiss = () => {
    setIsExiting(true);
    setTimeout(onDismiss, 300);
  };

  const handleTrackingClick = () => {
    navigate('/game/history');
    handleManualDismiss();
  };

  // Format message: "{username} {action} your {role} submission of \"{phrase}\""
  const icon = notification.action === 'copied' ? '📝' : '🗳️';
  const message = `${notification.actor_username} ${notification.action} your ${notification.recipient_role} submission of "${notification.phrase_text}"`;

  return (
    <div
      className={`
        tile-card p-4 max-w-sm
        bg-gradient-to-r from-ccl-turquoise to-teal-500
        shadow-lg
        transition-all duration-300
        ${isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <span className="text-2xl flex-shrink-0">{icon}</span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-white font-semibold text-sm leading-snug break-words">
            {message}
          </p>

          {/* Tracking button */}
          <button
            onClick={handleTrackingClick}
            className="mt-2 flex items-center gap-1 text-white/90 hover:text-white text-xs transition-colors"
          >
            <TrackingIcon className="w-4 h-4 flex-shrink-0" />
            <span className="underline">Visit history page</span>
          </button>
        </div>

        {/* Close button */}
        <button
          onClick={handleManualDismiss}
          className="text-white/80 hover:text-white text-lg flex-shrink-0 leading-none"
          aria-label="Dismiss notification"
        >
          ×
        </button>
      </div>
    </div>
  );
};

export default NotificationToast;
