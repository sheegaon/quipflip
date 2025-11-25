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
  useCallback,
} from 'react';
import { useGame } from './GameContext';
import apiClient from '../api/client';
import { NotificationStreamMessage, OnlineUser } from '../api/types';
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
  onlineUsers: OnlineUser[];
  totalCount: number;
  loadingOnlineUsers: boolean;
  onlineUsersError: string | null;
  onlineUsersConnected: boolean;
  pingStatus: Record<string, 'idle' | 'sending' | 'sent'>;
  handlePingUser: (username: string) => Promise<void>;
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
  const onlineUsersWsRef = useRef<WebSocket | null>(null);
  const notificationIdRef = useRef(0);
  const pingIdRef = useRef(0);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { schedule, clear, resetAttempts } = useExponentialBackoff();
  const {
    schedule: scheduleOnlineUsers,
    clear: clearOnlineUsers,
    resetAttempts: resetOnlineUsersAttempts,
  } = useExponentialBackoff();
  const { state } = useGame();

  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingOnlineUsers, setLoadingOnlineUsers] = useState(true);
  const [onlineUsersError, setOnlineUsersError] = useState<string | null>(null);
  const [onlineUsersConnected, setOnlineUsersConnected] = useState(false);
  const [pingStatus, setPingStatus] = useState<Record<string, 'idle' | 'sending' | 'sent'>>({});

  const stopPollingOnlineUsers = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  const fetchOnlineUsers = useCallback(async () => {
    if (!state.isAuthenticated) return;

    try {
      const data = await apiClient.getOnlineUsers();
      setOnlineUsers(data.users);
      setTotalCount(data.total_count);
      setLoadingOnlineUsers(false);
      setOnlineUsersError((prev) => (prev && prev.includes('WebSocket unavailable') ? null : prev));
    } catch (err) {
      console.error('Failed to fetch online users:', err);
      setOnlineUsersError((prev) => prev ?? 'Failed to load online users');
    }
  }, [state.isAuthenticated]);

  const startPollingOnlineUsers = useCallback(() => {
    if (pollingIntervalRef.current) return;

    setOnlineUsersError((prev) => prev ?? 'Using polling mode (WebSocket unavailable)');
    fetchOnlineUsers();
    pollingIntervalRef.current = setInterval(fetchOnlineUsers, 10000);
  }, [fetchOnlineUsers]);

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

  useEffect(() => {
    let isMounted = true;

    const scheduleReconnect = () => {
      if (!state.isAuthenticated) return;

      scheduleOnlineUsers(() => {
        connectWebSocket();
      });
    };

    const connectWebSocket = async () => {
      if (!state.isAuthenticated || onlineUsersWsRef.current) return;

      try {
        const { token } = await apiClient.getWebsocketToken();
        const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
        const backendWsUrl = import.meta.env.VITE_BACKEND_WS_URL || 'wss://quipflip-c196034288cd.herokuapp.com';
        let wsUrl: string;

        if (apiUrl.startsWith('/')) {
          wsUrl = `${backendWsUrl}/qf/users/online/ws`;
        } else {
          wsUrl = apiUrl
            .replace('http://', 'ws://')
            .replace('https://', 'wss://') + '/qf/users/online/ws';
        }

        wsUrl += `?token=${encodeURIComponent(token)}`;

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (!isMounted) return;
          setOnlineUsersConnected(true);
          setOnlineUsersError(null);
          setLoadingOnlineUsers(false);
          resetOnlineUsersAttempts();
          clearOnlineUsers();
          stopPollingOnlineUsers();
        };

        ws.onmessage = (event) => {
          try {
            const data: {
              type: string;
              users: OnlineUser[];
              total_count: number;
              timestamp: string;
            } = JSON.parse(event.data);

            if (data.type === 'online_users_update') {
              setOnlineUsers(data.users);
              setTotalCount(data.total_count);
            }
          } catch {
            // Silently ignore malformed messages
          }
        };

        ws.onerror = () => {
          if (!isMounted) return;
          setOnlineUsersConnected(false);
          ws.close();
        };

        ws.onclose = (event) => {
          if (!isMounted) return;
          onlineUsersWsRef.current = null;
          setOnlineUsersConnected(false);

          if (event.code === 1008) {
            setOnlineUsersError('Authentication failed. Please log in again.');
            setLoadingOnlineUsers(false);
            stopPollingOnlineUsers();
            return;
          }

          startPollingOnlineUsers();
          scheduleReconnect();
        };

        onlineUsersWsRef.current = ws;
      } catch {
        if (!isMounted) return;
        setOnlineUsersConnected(false);
        onlineUsersWsRef.current = null;
        startPollingOnlineUsers();
        scheduleReconnect();
      }
    };

    if (state.isAuthenticated) {
      connectWebSocket();
    } else {
      stopPollingOnlineUsers();
      clearOnlineUsers();
      resetOnlineUsersAttempts();
      setOnlineUsers([]);
      setTotalCount(0);
      setPingStatus({});
      setOnlineUsersConnected(false);
      setOnlineUsersError(null);
      setLoadingOnlineUsers(false);
      if (onlineUsersWsRef.current) {
        onlineUsersWsRef.current.close(1000, 'User not authenticated');
        onlineUsersWsRef.current = null;
      }
    }

    return () => {
      isMounted = false;
      stopPollingOnlineUsers();
      clearOnlineUsers();
      resetOnlineUsersAttempts();

      if (onlineUsersWsRef.current) {
        onlineUsersWsRef.current.close(1000, 'Component unmounting');
        onlineUsersWsRef.current = null;
      }

      setOnlineUsersConnected(false);
    };
  }, [
    clearOnlineUsers,
    resetOnlineUsersAttempts,
    scheduleOnlineUsers,
    startPollingOnlineUsers,
    state.isAuthenticated,
    stopPollingOnlineUsers,
  ]);

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

  const handlePingUser = useCallback(async (username: string) => {
    setPingStatus((prev) => ({ ...prev, [username]: 'sending' }));

    try {
      await apiClient.pingOnlineUser(username);
      setPingStatus((prev) => ({ ...prev, [username]: 'sent' }));

      setTimeout(() => {
        setPingStatus((prev) => ({ ...prev, [username]: 'idle' }));
      }, 3000);
    } catch (err) {
      console.error('Failed to ping user:', err);
      setPingStatus((prev) => ({ ...prev, [username]: 'idle' }));
    }
  }, []);

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        addNotification,
        removeNotification,
        clearAll,
        pingMessages,
        removePingMessage,
        onlineUsers,
        totalCount,
        loadingOnlineUsers,
        onlineUsersError,
        onlineUsersConnected,
        pingStatus,
        handlePingUser,
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
