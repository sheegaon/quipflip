import React from 'react';

export interface ErrorNotificationProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
  icon?: string;
}

export const ErrorNotification: React.FC<ErrorNotificationProps> = ({
  message,
  onDismiss,
  className = '',
  icon = '⚠️',
}) => {
  return (
    <div className={`tile-card bg-red-50 border border-red-200 ${className}`} role="alert">
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden>{icon}</span>
        <div className="flex-1">
          <p className="text-red-800 font-medium">{message}</p>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-red-500 hover:text-red-700"
            aria-label="Dismiss error"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorNotification;
