import React from 'react';

export interface SuccessNotificationProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
  icon?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const SuccessNotification: React.FC<SuccessNotificationProps> = ({
  message,
  onDismiss,
  className = '',
  icon = '✅',
  actionLabel,
  onAction,
}) => {
  return (
    <div className={`tile-card bg-green-50 border border-green-200 ${className}`} role="status">
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden>{icon}</span>
        <div className="flex-1 space-y-2">
          <p className="text-green-800 font-medium">{message}</p>
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className="btn btn-primary btn-sm"
            >
              {actionLabel}
            </button>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-green-500 hover:text-green-700"
            aria-label="Dismiss notification"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default SuccessNotification;
