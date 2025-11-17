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
        // Step 1: Fetch short-lived WebSocket token via REST API
        const tokenResponse = await fetch('/ir/api/auth/ws-token', {
          credentials: 'include', // Include HttpOnly cookies
        });

        if (!tokenResponse.ok) {
          throw new Error('Failed to get WebSocket token');
        }

        const { token } = await tokenResponse.json();

        // Step 2: Construct WebSocket URL for direct connection
        const apiUrl =
          import.meta.env.VITE_API_URL ||
          `http://${window.location.hostname}:8000/ir`;
        const backendWsUrl =
          import.meta.env.VITE_BACKEND_WS_URL ||
          'wss://quipflip-c196034288cd.herokuapp.com';

        let wsUrl: string;

        if (apiUrl.startsWith('/')) {
          // Production: use direct Heroku connection
          wsUrl = `${backendWsUrl}/ir/notifications/ws`;
        } else {
          // Development: connect directly to local backend
          wsUrl = apiUrl
            .replace('http://', 'ws://')
            .replace('https://', 'wss://') + '/notifications/ws';
        }

        // Step 3: Add short-lived token as query parameter
        wsUrl += `?token=${encodeURIComponent(token)}`;

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
