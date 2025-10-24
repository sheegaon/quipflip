import React, { useEffect, useState } from 'react';

interface SuccessNotificationProps {
  message: string;
  onDismiss?: () => void;
  autoHide?: boolean;
  duration?: number;
  actionLabel?: string;
  onAction?: () => void;
  icon?: string;
}

export const SuccessNotification: React.FC<SuccessNotificationProps> = ({
  message,
  onDismiss,
  autoHide = true,
  duration = 5000,
  actionLabel,
  onAction,
  icon = '🎉'
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => {
      if (onDismiss) {
        onDismiss();
      }
      setIsVisible(false);
      setIsExiting(false);
    }, 300);
  };

  useEffect(() => {
    if (message) {
      setIsVisible(true);
      setIsExiting(false);

      if (autoHide) {
        // Auto-dismiss after specified duration
        const timeout = setTimeout(() => {
          handleDismiss();
        }, duration);

        return () => clearTimeout(timeout);
      }
    } else {
      setIsVisible(false);
    }
  }, [message, autoHide, duration]);

  if (!message || !isVisible) return null;

  return (
    <div className={`fixed top-4 right-4 z-50 max-w-md transition-all duration-300 ${
      isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'
    }`}>
      <div className="bg-gradient-to-r from-quip-turquoise to-teal-500 text-white rounded-lg shadow-lg overflow-hidden">
        {/* Progress bar for auto-hide */}
        {autoHide && (
          <div className="h-1 bg-black bg-opacity-20">
            <div
              className="h-full bg-white bg-opacity-50 transition-all ease-linear"
              style={{
                width: '100%',
                animation: `shrink ${duration}ms linear forwards`
              }}
            />
          </div>
        )}

        <div className="p-4">
          <div className="flex items-start gap-3">
            <div className="text-xl flex-shrink-0">
              {icon}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <p className="font-semibold text-sm">Success!</p>
                <button
                  onClick={handleDismiss}
                  className="text-white hover:text-gray-200 font-bold text-xl leading-none ml-2 flex-shrink-0"
                  aria-label="Dismiss notification"
                >
                  ×
                </button>
              </div>

              <p className="text-sm leading-relaxed">{message}</p>

              {/* Action button if provided */}
              {actionLabel && onAction && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => {
                      onAction();
                      handleDismiss();
                    }}
                    className="text-xs bg-white bg-opacity-20 hover:bg-opacity-30 px-3 py-1 rounded transition-colors"
                  >
                    {actionLabel}
                  </button>
                  <button
                    onClick={handleDismiss}
                    className="text-xs text-white text-opacity-70 hover:text-opacity-100 px-3 py-1 transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* CSS animation for progress bar */}
      <style>
        {`
          @keyframes shrink {
            from { width: 100%; }
            to { width: 0%; }
          }
        `}
      </style>
    </div>
  );
};
