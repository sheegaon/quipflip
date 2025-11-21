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

/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  ReactNode,
  FC,
} from 'react';
import { useGame } from './GameContext';
import apiClient from '../api/client';
import { NotificationStreamMessage } from '../api/types';
import useExponentialBackoff from '../hooks/useExponentialBackoff';

export interface NotificationMessage {
  id: string;
  actor_username: string;
  action: 'copied' | 'voted on';
  recipient_role: 'prompt' | 'copy';
  phrase_text: string;
  timestamp: string;
}

interface NotificationContextType {
  notifications: NotificationMessage[];
  addNotification: (message: NotificationMessage) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  pingMessages: PingToastMessage[];
  removePingMessage: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined
);

interface NotificationProviderProps {
  children: ReactNode;
}

interface PingToastMessage {
  id: string;
  message: string;
  timestamp: string;
  joinUrl?: string;
}

export const NotificationProvider: FC<NotificationProviderProps> = ({
  children,
}) => {
  const [notifications, setNotifications] = useState<NotificationMessage[]>([]);
  const [pingMessages, setPingMessages] = useState<PingToastMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const notificationIdRef = useRef(0);
  const pingIdRef = useRef(0);
  const { schedule, clear, resetAttempts } = useExponentialBackoff();
  const { state } = useGame();

  useEffect(() => {
    const scheduleReconnect = () => {
      if (!state.isAuthenticated) return;

      schedule(() => {
        connectWebSocket();
      });
    };

    const connectWebSocket = async () => {
      if (!state.isAuthenticated || wsRef.current) return;

      try {
        // Step 1: Fetch short-lived WebSocket token via REST API (through Vercel proxy)
        const { token } = await apiClient.getWebsocketToken();

        // Step 2: Construct WebSocket URL for direct connection to Heroku
        const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
        const backendWsUrl = import.meta.env.VITE_BACKEND_WS_URL || 'wss://quipflip-c196034288cd.herokuapp.com';
        let wsUrl: string;

        if (apiUrl.startsWith('/')) {
          // Production: use direct Heroku connection (cannot proxy WebSocket through Vercel)
          wsUrl = `${backendWsUrl}/qf/notifications/ws`;
        } else {
          // Development: connect directly to local backend
          wsUrl = apiUrl
            .replace('http://', 'ws://')
            .replace('https://', 'wss://') + '/qf/notifications/ws';
        }

        // Step 3: Add short-lived token as query parameter
        wsUrl += `?token=${encodeURIComponent(token)}`;

        // Create WebSocket connection
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('WebSocket connected for notifications');
          clear();
          resetAttempts();
        };

        ws.onmessage = (event) => {
          try {
            const data: NotificationStreamMessage = JSON.parse(event.data);

            if (data.type === 'notification') {
              const notification: NotificationMessage = {
                id: `notification-${++notificationIdRef.current}`,
                actor_username: data.actor_username,
                action: data.action,
                recipient_role: data.recipient_role,
                phrase_text: data.phrase_text,
                timestamp: data.timestamp,
              };

              setNotifications((prev) => [...prev, notification]);
              return;
            }

            if (data.type === 'ping') {
              const ping: PingToastMessage = {
                id: `ping-${++pingIdRef.current}`,
                message: data.join_url
                  ? `${data.from_username} pinged your party`
                  : `${data.from_username} has pinged you`,
                timestamp: data.timestamp,
                joinUrl: data.join_url,
              };

              setPingMessages((prev) => [...prev, ping]);
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
          console.debug('WebSocket disconnected, attempting reconnect');
          wsRef.current = null;
          scheduleReconnect();
        };

        wsRef.current = ws;
      } catch (err) {
        // Fail silently but schedule reconnect so pings continue working
        console.debug('WebSocket connection failed silently:', err);
        wsRef.current = null;
        scheduleReconnect();
      }
    };

    if (state.isAuthenticated) {
      connectWebSocket();
    } else {
      clear();
      resetAttempts();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }

    // Cleanup on unmount or logout
    return () => {
      clear();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      resetAttempts();
    };
  }, [clear, resetAttempts, schedule, state.isAuthenticated]);

  const addNotification = (message: NotificationMessage) => {
    setNotifications((prev) => [...prev, message]);
  };

  const removeNotification = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const removePingMessage = (id: string) => {
    setPingMessages((prev) => prev.filter((ping) => ping.id !== id));
  };

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        addNotification,
        removeNotification,
        clearAll,
        pingMessages,
        removePingMessage,
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
