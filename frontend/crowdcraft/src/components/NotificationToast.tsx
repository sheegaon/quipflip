import { FC, useEffect, useState } from 'react';
import { NotificationMessage } from '../contexts/NotificationContext';
import { TrackingIcon } from './icons/NavigationIcons.tsx';

export interface NotificationToastProps {
  notification: NotificationMessage;
  onDismiss: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

const NotificationToast: FC<NotificationToastProps> = ({
  notification,
  onDismiss,
  actionLabel,
  onAction,
}) => {
  const [isExiting, setIsExiting] = useState(false);

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(onDismiss, 300);
    }, 5000);

    return () => clearTimeout(timer);
  }, [onDismiss]);

  const handleManualDismiss = () => {
    setIsExiting(true);
    setTimeout(onDismiss, 300);
  };

  const handleActionClick = () => {
    if (!onAction) return;
    onAction();
    handleManualDismiss();
  };

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
        <span className="text-2xl flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-white font-semibold text-sm leading-snug break-words">
            {message}
          </p>

          {actionLabel && onAction && (
            <button
              onClick={handleActionClick}
              className="mt-2 flex items-center gap-1 text-white/90 hover:text-white text-xs transition-colors"
            >
              <TrackingIcon className="w-4 h-4 flex-shrink-0" />
              <span className="underline">{actionLabel}</span>
            </button>
          )}
        </div>

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
