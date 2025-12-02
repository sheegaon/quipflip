import React from 'react';

export interface OfflineBannerProps {
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

const OfflineBanner: React.FC<OfflineBannerProps> = ({
  message = 'You are offline. Some features may be limited.',
  actionLabel,
  onAction,
}) => {
  return (
    <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 p-3 rounded-lg shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-yellow-500">⚠️</span>
          <p className="font-medium">{message}</p>
        </div>
        {actionLabel && onAction && (
          <button
            onClick={onAction}
            className="btn btn-secondary btn-sm"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
};

export default OfflineBanner;
