import { useState, useEffect, useCallback } from 'react';
import { networkLogger } from '@crowdcraft/utils/logger.ts';

type NavigatorConnection = EventTarget & {
  type?: string;
  effectiveType?: string;
};

interface ExtendedNavigator extends Navigator {
  connection?: NavigatorConnection;
  mozConnection?: NavigatorConnection;
  webkitConnection?: NavigatorConnection;
}

export interface NetworkStatus {
  isOnline: boolean;
  isOffline: boolean;
  wasOffline: boolean; // Track if user was recently offline
  connectionType?: string;
  effectiveConnectionType?: string;
}

const OFFLINE_STATE_KEY = 'quipflip_was_offline';

/**
 * Custom hook to monitor network status
 *
 * Tracks online/offline state and connection quality changes
 * Persists offline state in localStorage to handle page refreshes
 *
 * @returns NetworkStatus object with current network state
 */
export const useNetworkStatus = (): NetworkStatus => {
  // Initialize online state from navigator
  const [isOnline, setIsOnline] = useState<boolean>(() => {
    if (typeof navigator !== 'undefined') {
      return navigator.onLine;
    }
    return true; // Default to online
  });

  // Track if user was recently offline (for showing "back online" messages)
  const [wasOffline, setWasOffline] = useState<boolean>(() => {
    try {
      return localStorage.getItem(OFFLINE_STATE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  // Get connection information (if available)
  const [connectionInfo, setConnectionInfo] = useState<{
    connectionType?: string;
    effectiveConnectionType?: string;
  }>({});

  /**
   * Update connection information from Network Information API
   */
  const updateConnectionInfo = useCallback(() => {
    const extendedNavigator = navigator as ExtendedNavigator;
    if (extendedNavigator.connection || extendedNavigator.mozConnection || extendedNavigator.webkitConnection) {
      const conn = extendedNavigator.connection || extendedNavigator.mozConnection || extendedNavigator.webkitConnection;

      if (conn) {
        setConnectionInfo({
          connectionType: conn.type,
          effectiveConnectionType: conn.effectiveType,
        });
      }
    }
  }, []);

  /**
   * Handle going online
   */
  const handleOnline = useCallback(() => {
    setIsOnline(true);

    // Mark that we were offline (to show recovery message)
    if (!isOnline) {
      setWasOffline(true);
      try {
        localStorage.setItem(OFFLINE_STATE_KEY, 'true');
      } catch (e) {
        networkLogger.error('Failed to update offline state:', e);
      }

      // Clear the wasOffline flag after a delay
      setTimeout(() => {
        setWasOffline(false);
        try {
          localStorage.removeItem(OFFLINE_STATE_KEY);
        } catch (e) {
          networkLogger.error('Failed to clear offline state:', e);
        }
      }, 5000); // Show "back online" message for 5 seconds
    }

    updateConnectionInfo();
  }, [isOnline, updateConnectionInfo]);

  /**
   * Handle going offline
   */
  const handleOffline = useCallback(() => {
    setIsOnline(false);
    try {
      localStorage.setItem(OFFLINE_STATE_KEY, 'true');
    } catch (e) {
      networkLogger.error('Failed to set offline state:', e);
    }
    updateConnectionInfo();
  }, [updateConnectionInfo]);

  /**
   * Handle connection change (for Network Information API)
   */
  const handleConnectionChange = useCallback(() => {
    updateConnectionInfo();
  }, [updateConnectionInfo]);

  /**
   * Set up event listeners
   */
  useEffect(() => {
    // Listen for online/offline events
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Listen for connection changes (if supported)
    const extendedNavigator = navigator as ExtendedNavigator;
    if (extendedNavigator.connection) {
      const conn = extendedNavigator.connection;
      if (conn) {
        conn.addEventListener('change', handleConnectionChange);
      }
    }

    // Initial connection info update
    updateConnectionInfo();

    // Cleanup
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);

      if ((navigator as ExtendedNavigator).connection) {
        const conn = (navigator as ExtendedNavigator).connection;
        if (conn) {
          conn.removeEventListener('change', handleConnectionChange);
        }
      }
    };
  }, [handleOnline, handleOffline, handleConnectionChange, updateConnectionInfo]);

  return {
    isOnline,
    isOffline: !isOnline,
    wasOffline,
    connectionType: connectionInfo.connectionType,
    effectiveConnectionType: connectionInfo.effectiveConnectionType,
  };
};

/**
 * Get a human-readable connection quality label
 */
export const getConnectionQuality = (effectiveType?: string): 'fast' | 'slow' | 'offline' => {
  if (!effectiveType) return 'fast';

  switch (effectiveType) {
    case '4g':
      return 'fast';
    case '3g':
      return 'slow';
    case '2g':
    case 'slow-2g':
      return 'slow';
    default:
      return 'fast';
  }
};
