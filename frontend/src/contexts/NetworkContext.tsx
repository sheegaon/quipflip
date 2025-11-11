import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNetworkStatus, getConnectionQuality } from '../hooks/useNetworkStatus';
import { offlineQueue, type OfflineAction } from '../utils/offlineQueue';

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
      console.warn('Cannot retry requests while offline');
      return;
    }

    const queue = offlineQueue.getQueue();
    console.log(`Retrying ${queue.length} queued requests...`);

    for (const action of queue) {
      // Check if action has exceeded max retries
      if (offlineQueue.hasExceededMaxRetries(action.id)) {
        console.warn(`Action ${action.id} has exceeded max retries, removing from queue`);
        offlineQueue.removeAction(action.id);
        continue;
      }

      try {
        // Attempt to replay the action
        const response = await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.data ? JSON.stringify(action.data) : undefined,
        });

        if (response.ok) {
          // Success! Remove from queue
          offlineQueue.removeAction(action.id);
          console.log(`Successfully synced action ${action.id}`);
        } else {
          // Failed, increment retry count
          offlineQueue.incrementRetryCount(action.id);
          console.warn(`Failed to sync action ${action.id}, will retry later`);
        }
      } catch (error) {
        // Network error, increment retry count
        offlineQueue.incrementRetryCount(action.id);
        console.error(`Error syncing action ${action.id}:`, error);
      }
    }
  }, [networkStatus.isOnline]);

  /**
   * Clear the offline queue
   */
  const clearOfflineQueue = useCallback(() => {
    offlineQueue.clearQueue();
    console.log('Offline queue cleared');
  }, []);

  /**
   * Auto-retry when coming back online
   */
  useEffect(() => {
    if (networkStatus.isOnline && networkStatus.wasOffline && queueSize > 0) {
      console.log('Back online! Auto-retrying queued requests...');
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
