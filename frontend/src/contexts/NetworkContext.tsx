import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNetworkStatus, getConnectionQuality } from '../hooks/useNetworkStatus';
import { offlineQueue, type OfflineAction } from '../utils/offlineQueue';
import { axiosInstance } from '../api/client';
import { networkLogger } from '../utils/logger';

export interface NetworkContextType {
  isOnline: boolean;
  isOffline: boolean;
  wasOffline: boolean;
  connectionQuality: 'fast' | 'slow' | 'offline';
  queueSize: number;
  retryFailedRequests: () => Promise<void>;
  clearOfflineQueue: () => void;
}

const NetworkContext = createContext<NetworkContextType | undefined>(undefined);

/**
 * NetworkProvider Component
 *
 * Provides network status and offline queue management to the entire app
 */
export const NetworkProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const networkStatus = useNetworkStatus();
  const [queueSize, setQueueSize] = useState(offlineQueue.getQueueSize());

  // Determine connection quality
  const connectionQuality = networkStatus.isOffline
    ? 'offline'
    : getConnectionQuality(networkStatus.effectiveConnectionType);

  /**
   * Subscribe to offline queue changes
   */
  useEffect(() => {
    const unsubscribe = offlineQueue.subscribe((queue: OfflineAction[]) => {
      setQueueSize(queue.length);
    });

    return unsubscribe;
  }, []);

  /**
   * Retry failed requests when coming back online
   */
  const retryFailedRequests = useCallback(async () => {
    if (!networkStatus.isOnline) {
      networkLogger.warn('Cannot retry requests while offline');
      return;
    }

    const queue = offlineQueue.getQueue();
    networkLogger.info(`Retrying ${queue.length} queued requests...`);

    for (const action of queue) {
      // Check if action has exceeded max retries
      if (offlineQueue.hasExceededMaxRetries(action.id)) {
        networkLogger.warn(`Action ${action.id} has exceeded max retries, removing from queue`);
        offlineQueue.removeAction(action.id);
        continue;
      }

      try {
        // Attempt to replay the action using Axios instance
        // This ensures we use the correct baseURL and credentials (withCredentials: true)
        await axiosInstance.request({
          method: action.method,
          url: action.url,
          data: action.data,
          headers: action.headers,
        });

        // Success! Remove from queue
        offlineQueue.removeAction(action.id);
        networkLogger.info(`Successfully synced action ${action.id}`);
      } catch (error: any) {
        // Check if it's a permanent error (4xx) vs transient (network, 5xx)
        const isPermanentError = error.response && error.response.status >= 400 && error.response.status < 500;

        if (isPermanentError && error.response.status !== 429) {
          // Permanent error (not rate limit) - remove from queue
          networkLogger.warn(`Action ${action.id} failed with permanent error ${error.response.status}, removing from queue`);
          offlineQueue.removeAction(action.id);
        } else {
          // Transient error - increment retry count
          offlineQueue.incrementRetryCount(action.id);
          networkLogger.warn(`Failed to sync action ${action.id}, will retry later`);
        }
      }
    }
  }, [networkStatus.isOnline]);

  /**
   * Clear the offline queue
   */
  const clearOfflineQueue = useCallback(() => {
    offlineQueue.clearQueue();
    networkLogger.info('Offline queue cleared');
  }, []);

  /**
   * Auto-retry when coming back online
   */
  useEffect(() => {
    if (networkStatus.isOnline && networkStatus.wasOffline && queueSize > 0) {
      networkLogger.info('Back online! Auto-retrying queued requests...');
      retryFailedRequests();
    }
  }, [networkStatus.isOnline, networkStatus.wasOffline, queueSize, retryFailedRequests]);

  const value: NetworkContextType = {
    isOnline: networkStatus.isOnline,
    isOffline: networkStatus.isOffline,
    wasOffline: networkStatus.wasOffline,
    connectionQuality,
    queueSize,
    retryFailedRequests,
    clearOfflineQueue,
  };

  return <NetworkContext.Provider value={value}>{children}</NetworkContext.Provider>;
};

/**
 * Hook to access network context
 */
export const useNetwork = (): NetworkContextType => {
  const context = useContext(NetworkContext);
  if (!context) {
    throw new Error('useNetwork must be used within a NetworkProvider');
  }
  return context;
};
