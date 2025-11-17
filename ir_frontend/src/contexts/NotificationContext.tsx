/**
 * Notification Context for WebSocket push notifications.
 *
 * Manages WebSocket connection lifecycle and maintains notification state.
 * Initializes connection when authenticated, closes on logout.
 * Fails silently if WebSocket is unavailable (no error messages, no polling).
 *
 * This is a pure state management context - it does NOT render notifications.
 * Use NotificationDisplay component for rendering.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  ReactNode,
  FC,
} from 'react';
import { useIRGame } from './IRGameContext';

export interface NotificationMessage {
  id: string;
  actor_username: string;
  action: 'voted on' | 'reacted to' | 'joined';
  set_id?: string;
  entry_text?: string;
  timestamp: string;
}

interface NotificationContextType {
  notifications: NotificationMessage[];
  addNotification: (message: NotificationMessage) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
);

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: FC<NotificationProviderProps> = ({
  children,
}) => {
  const [notifications, setNotifications] = useState<NotificationMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const notificationIdRef = useRef(0);
  const { isAuthenticated } = useIRGame();

  useEffect(() => {
    let wsAttempted = false;

    // Connect when authenticated
    const connectWebSocket = async () => {
      if (wsAttempted) return; // Prevent multiple attempts
      wsAttempted = true;

      try {
        // Step 1: Construct API base URL preserving the path prefix
        const apiBase =
          import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000/ir`;

        // Normalize base URL - ensure it's a full URL and remove trailing slash
        const baseUrl = apiBase.startsWith('http')
          ? apiBase.replace(/\/$/, '')
          : `${window.location.origin}${apiBase}`.replace(/\/$/, '');

        // Step 2: Fetch short-lived WebSocket token via REST API
        // Construct URL by appending to base (no leading slash to preserve path)
        const tokenUrl = `${baseUrl}/auth/ws-token`;
        const tokenResponse = await fetch(tokenUrl, {
          credentials: 'include', // Include HttpOnly cookies
        });

        if (!tokenResponse.ok) {
          throw new Error('Failed to get WebSocket token');
        }

        const { token } = await tokenResponse.json();

        // Step 3: Construct WebSocket URL preserving the base path
        const wsBaseUrl = baseUrl
          .replace('http://', 'ws://')
          .replace('https://', 'wss://');

        const wsUrl = `${wsBaseUrl}/notifications/ws?token=${encodeURIComponent(token)}`;

        // Create WebSocket connection
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('WebSocket connected for notifications');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'notification') {
              const notification: NotificationMessage = {
                id: `notification-${++notificationIdRef.current}`,
                actor_username: data.actor_username,
                action: data.action || 'reacted to',
                set_id: data.set_id,
                entry_text: data.entry_text,
                timestamp: data.timestamp,
              };

              setNotifications((prev) => [...prev, notification]);
            }
          } catch (err) {
            // Silently ignore malformed messages
            console.error('Failed to parse notification message:', err);
          }
        };

        ws.onerror = () => {
          // Fail silently - no error message to user
          console.debug('WebSocket error, connection failed silently');
        };

        ws.onclose = () => {
          // Fail silently - no reconnect attempts
          console.debug('WebSocket disconnected, no reconnect');
        };

        wsRef.current = ws;
      } catch (err) {
        // Fail silently
        console.debug('WebSocket connection failed silently:', err);
      }
    };

    if (isAuthenticated) {
      connectWebSocket();
    }

    // Cleanup on unmount or logout
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isAuthenticated]);

  const addNotification = (message: NotificationMessage) => {
    setNotifications((prev) => [...prev, message]);
  };

  const removeNotification = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        addNotification,
        removeNotification,
        clearAll,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      'useNotifications must be used within NotificationProvider'
    );
  }
  return context;
};
