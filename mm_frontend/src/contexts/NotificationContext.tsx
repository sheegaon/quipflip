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
  useRef,
  ReactNode,
  FC,
  useCallback,
  useEffect,
} from 'react';
import { useGame } from './GameContext';
import apiClient from '../api/client';
import { NotificationStreamMessage, OnlineUser } from '../api/types';
import useWebSocket from '../hooks/useWebSocket';

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
  const notificationsEnabled = import.meta.env.VITE_ENABLE_NOTIFICATIONS === 'true';
  const onlineUsersEnabled = import.meta.env.VITE_ENABLE_ONLINE_USERS === 'true';

  const [notifications, setNotifications] = useState<NotificationMessage[]>([]);
  const [pingMessages, setPingMessages] = useState<PingToastMessage[]>([]);
  const notificationIdRef = useRef(0);
  const pingIdRef = useRef(0);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { state } = useGame();

  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingOnlineUsers, setLoadingOnlineUsers] = useState(true);
  const [onlineUsersError, setOnlineUsersError] = useState<string | null>(null);
  const [onlineUsersConnected, setOnlineUsersConnected] = useState(false);
  const [pingStatus, setPingStatus] = useState<Record<string, 'idle' | 'sending' | 'sent'>>({});
  const pingResetTimeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearPingTimeouts = useCallback(() => {
    pingResetTimeoutsRef.current.forEach(clearTimeout);
    pingResetTimeoutsRef.current = [];
  }, []);

  const stopPollingOnlineUsers = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  const fetchOnlineUsers = useCallback(async () => {
    if (!state.isAuthenticated || !onlineUsersEnabled) {
      setLoadingOnlineUsers(false);
      return;
    }

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
  }, [onlineUsersEnabled, state.isAuthenticated]);

  const startPollingOnlineUsers = useCallback(() => {
    if (pollingIntervalRef.current || !onlineUsersEnabled) return;

    setOnlineUsersError((prev) => prev ?? 'Using polling mode (WebSocket unavailable)');
    fetchOnlineUsers();
    pollingIntervalRef.current = setInterval(fetchOnlineUsers, 10000);
  }, [fetchOnlineUsers, onlineUsersEnabled]);

  const handleNotificationMessage = useCallback((event: MessageEvent) => {
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
  }, []);

  useWebSocket({
    path: '/notifications/ws',
    enabled: state.isAuthenticated && notificationsEnabled,
    onMessage: handleNotificationMessage,
    onError: () => {
      console.debug('WebSocket error, connection failed silently');
    },
    onConnectError: () => {
      console.debug('WebSocket connection failed silently');
    },
  });

  const handleOnlineUsersOpen = useCallback(() => {
    setOnlineUsersConnected(true);
    setOnlineUsersError(null);
    setLoadingOnlineUsers(false);
    stopPollingOnlineUsers();
  }, [stopPollingOnlineUsers]);

  const handleOnlineUsersMessage = useCallback((event: MessageEvent) => {
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
  }, []);

  const handleOnlineUsersError = useCallback(
    (_event: Event, socket: WebSocket) => {
      setOnlineUsersConnected(false);
      socket.close();
    },
    []
  );

  const handleOnlineUsersClose = useCallback(
    (event: CloseEvent) => {
      setOnlineUsersConnected(false);

      if (event.code === 1008) {
        setOnlineUsersError('Authentication failed. Please log in again.');
        setLoadingOnlineUsers(false);
        stopPollingOnlineUsers();
        return false;
      }

      startPollingOnlineUsers();
      return true;
    },
    [startPollingOnlineUsers, stopPollingOnlineUsers]
  );

  const handleOnlineUsersConnectError = useCallback(() => {
    setOnlineUsersConnected(false);
    startPollingOnlineUsers();
    return true;
  }, [startPollingOnlineUsers]);

  useWebSocket({
    path: '/users/online/ws',
    enabled: state.isAuthenticated && onlineUsersEnabled,
    onOpen: handleOnlineUsersOpen,
    onMessage: handleOnlineUsersMessage,
    onError: handleOnlineUsersError,
    onClose: handleOnlineUsersClose,
    onConnectError: handleOnlineUsersConnectError,
  });

  useEffect(() => {
    if (!state.isAuthenticated || !onlineUsersEnabled) {
      stopPollingOnlineUsers();
      clearPingTimeouts();
      setOnlineUsers([]);
      setTotalCount(0);
      setPingStatus({});
      setOnlineUsersConnected(false);
      setLoadingOnlineUsers(false);
      setOnlineUsersError(onlineUsersEnabled ? null : 'Online users are disabled');
    }
  }, [
    state.isAuthenticated,
    stopPollingOnlineUsers,
    clearPingTimeouts,
    onlineUsersEnabled,
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

      const timeoutId = setTimeout(() => {
        setPingStatus((prev) => ({ ...prev, [username]: 'idle' }));
      }, 3000);
      pingResetTimeoutsRef.current.push(timeoutId);
    } catch (err) {
      console.error('Failed to ping user:', err);
      setPingStatus((prev) => ({ ...prev, [username]: 'idle' }));
    }
  }, []);

  useEffect(() => {
    return () => {
      stopPollingOnlineUsers();
      clearPingTimeouts();
    };
  }, [stopPollingOnlineUsers, clearPingTimeouts]);

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
