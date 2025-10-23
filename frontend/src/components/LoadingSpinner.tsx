import React from 'react';

export interface LoadingState {
  isLoading: boolean;
  type?: 'initial' | 'submit' | 'refresh' | 'sync' | 'retry';
  message?: string;
  progress?: number;
  isOffline?: boolean;
  queuedAction?: boolean;
  canCancel?: boolean;
  onCancel?: () => void;
}

interface LoadingSpinnerProps extends LoadingState {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  isLoading,
  type = 'initial',
  message,
  progress,
  isOffline = false,
  queuedAction = false,
  canCancel = false,
  onCancel,
  size = 'md',
  className = '',
}) => {
  if (!isLoading) return null;

  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  const containerClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  // Different loading messages based on context
  const getLoadingMessage = () => {
    if (message) return message;
    
    if (isOffline && queuedAction) {
      return "Action queued - will sync when online";
    }
    
    if (isOffline) {
      return "Working offline...";
    }

    switch (type) {
      case 'submit':
        return "Submitting...";
      case 'refresh':
        return "Refreshing...";
      case 'sync':
        return "Syncing your data...";
      case 'retry':
        return "Retrying...";
      default:
        return "Loading...";
    }
  };

  // Different spinner colors based on state
  const getSpinnerColor = () => {
    if (isOffline) return 'text-orange-500';
    if (queuedAction) return 'text-yellow-500';
    if (type === 'retry') return 'text-blue-500';
    return 'text-quip-teal';
  };

  const getStatusIcon = () => {
    if (isOffline && queuedAction) return '📤';
    if (isOffline) return '🔄';
    if (type === 'retry') return '↻';
    if (type === 'sync') return '🔄';
    return null;
  };

  return (
    <div className={`flex flex-col items-center justify-center p-4 ${containerClasses[size]} ${className}`}>
      <div className="flex items-center gap-3 mb-2">
        {/* Status icon */}
        {getStatusIcon() && (
          <span className="text-lg">{getStatusIcon()}</span>
        )}
        
        {/* Spinner */}
        <div className={`${sizeClasses[size]} ${getSpinnerColor()} animate-spin`}>
          <svg
            className="w-full h-full"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </div>
      </div>

      {/* Loading message */}
      <p className="text-center text-gray-600 dark:text-gray-300 mb-2">
        {getLoadingMessage()}
      </p>

      {/* Progress bar */}
      {progress !== undefined && progress >= 0 && (
        <div className="w-full max-w-xs mb-2">
          <div className="bg-gray-200 rounded-full h-2">
            <div
              className="bg-quip-teal h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1 text-center">
            {Math.round(progress)}%
          </p>
        </div>
      )}

      {/* Offline status */}
      {isOffline && (
        <div className="text-xs text-orange-600 bg-orange-50 px-3 py-1 rounded-full mb-2">
          ⚠️ Working offline
        </div>
      )}

      {/* Queued action status */}
      {queuedAction && !isOffline && (
        <div className="text-xs text-yellow-600 bg-yellow-50 px-3 py-1 rounded-full mb-2">
          📤 Action queued for sync
        </div>
      )}

      {/* Cancel button */}
      {canCancel && onCancel && (
        <button
          onClick={onCancel}
          className="text-xs text-gray-500 hover:text-gray-700 underline mt-2 transition-colors"
        >
          Cancel
        </button>
      )}
    </div>
  );
};

// Hook for managing loading states with context
export const useLoadingState = () => {
  const [loadingStates, setLoadingStates] = React.useState<Record<string, LoadingState>>({});

  const setLoading = (key: string, state: LoadingState) => {
    setLoadingStates(prev => ({
      ...prev,
      [key]: state
    }));
  };

  const clearLoading = (key: string) => {
    setLoadingStates(prev => {
      const newState = { ...prev };
      delete newState[key];
      return newState;
    });
  };

  const isAnyLoading = Object.values(loadingStates).some(state => state.isLoading);
  const getLoadingState = (key: string) => loadingStates[key];

  return {
    setLoading,
    clearLoading,
    isAnyLoading,
    getLoadingState,
    loadingStates
  };
};

// Specific loading components for common use cases
export const SubmitLoadingSpinner: React.FC<{ message?: string; isOffline?: boolean }> = ({ 
  message, 
  isOffline 
}) => (
  <LoadingSpinner
    isLoading={true}
    type="submit"
    message={message}
    isOffline={isOffline}
    size="sm"
  />
);

export const PageLoadingSpinner: React.FC<{ message?: string }> = ({ message }) => (
  <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
    <LoadingSpinner
      isLoading={true}
      type="initial"
      message={message}
      size="lg"
    />
  </div>
);

export const InlineLoadingSpinner: React.FC<{ message?: string; type?: LoadingState['type'] }> = ({ 
  message, 
  type = 'refresh' 
}) => (
  <LoadingSpinner
    isLoading={true}
    type={type}
    message={message}
    size="sm"
    className="py-2"
  />
);
