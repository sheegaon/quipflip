import React, { useState, useEffect } from 'react';
import { useNetwork } from '../contexts/NetworkContext';
import { networkLogger } from '@crowdcraft/utils/logger.ts';

/**
 * OfflineBanner Component
 *
 * Displays a persistent banner when offline and a celebration when back online
 * Shows queued action count and provides manual retry button
 */
export const OfflineBanner: React.FC = () => {
  const { isOffline, wasOffline, queueSize, retryFailedRequests } = useNetwork();
  const [isRetrying, setIsRetrying] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);

  /**
   * Show celebration animation when back online
   */
  useEffect(() => {
    if (!isOffline && wasOffline) {
      setShowCelebration(true);
      const timer = setTimeout(() => {
        setShowCelebration(false);
      }, 3000); // Show for 3 seconds

      return () => clearTimeout(timer);
    }
  }, [isOffline, wasOffline]);

  /**
   * Handle manual retry
   */
  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await retryFailedRequests();
    } catch (error) {
      networkLogger.error('Failed to retry requests:', error);
    } finally {
      setIsRetrying(false);
    }
  };

  // Show celebration when back online
  if (showCelebration && !isOffline) {
    return (
      <div
        className="fixed top-0 left-0 right-0 z-50 bg-green-500 text-white px-4 py-3 text-center shadow-lg animate-slide-down"
        role="alert"
      >
        <div className="flex items-center justify-center gap-2">
          <span className="text-lg">✅</span>
          <span className="font-semibold">Connection restored!</span>
          {queueSize > 0 && <span className="text-sm opacity-90">Syncing {queueSize} action{queueSize !== 1 ? 's' : ''}...</span>}
        </div>
      </div>
    );
  }

  // Show offline banner
  if (isOffline) {
    return (
      <div
        className="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-yellow-900 px-4 py-3 text-center shadow-lg"
        role="alert"
      >
        <div className="flex flex-col sm:flex-row items-center justify-center gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-yellow-800 rounded-full animate-pulse"></span>
            <span className="font-semibold">You're offline</span>
            <span className="text-sm hidden sm:inline">Actions will sync when connection returns</span>
          </div>

          {queueSize > 0 && (
            <div className="flex items-center gap-2">
              <span className="bg-yellow-600 px-2 py-1 rounded text-xs font-semibold text-white">
                {queueSize} pending
              </span>
            </div>
          )}

          {!isOffline && queueSize > 0 && (
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="bg-yellow-700 hover:bg-yellow-800 disabled:bg-yellow-600 disabled:cursor-not-allowed text-white px-3 py-1 rounded text-sm font-semibold transition-colors"
            >
              {isRetrying ? 'Retrying...' : 'Retry Now'}
            </button>
          )}
        </div>

        {/* Mobile-friendly message */}
        <div className="text-xs mt-1 sm:hidden opacity-90">
          Actions will sync when connection returns
        </div>
      </div>
    );
  }

  return null;
};

/**
 * ConnectionIndicator Component
 *
 * Small indicator for Header or other components
 */
export const ConnectionIndicator: React.FC = () => {
  const { isOffline } = useNetwork();

  if (!isOffline) {
    return null;
  }

  return (
    <div
      className="w-2 h-2 bg-red-500 rounded-full animate-pulse"
      title="Offline"
      aria-label="You are currently offline"
    />
  );
};
