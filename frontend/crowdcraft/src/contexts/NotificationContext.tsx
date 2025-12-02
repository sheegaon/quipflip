/**
 * Notification Context for WebSocket push notifications.
 *
 * Shared implementation that supports per-game configuration for optional
 * features like online users, party web sockets, and feature flags.
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
import apiClient from '@/api/client';
import { NotificationStreamMessage, OnlineUser } from '@crowdcraft/api/types.ts';
import useWebSocket from '@crowdcraft/hooks/useWebSocket.ts';

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

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export interface PingToastMessage {
  id: string;
  message: string;
  timestamp: string;
  joinUrl?: string;
}

export interface NotificationContextConfig {
  notificationsEnabled: () => boolean;
  onlineUsersEnabled: () => boolean;
  partyPageContext?: string;
  usePartySessionId?: () => string | null;
  usePartyWebSocket?: (config: { sessionId: string; pageContext: string }) => void;
}

interface NotificationProviderProps {
  children: ReactNode;
  isAuthenticated: boolean;
  config: NotificationContextConfig;
}

export const createNotificationContext = () => {
  const NotificationProvider: FC<NotificationProviderProps> = ({
    children,
    isAuthenticated,
    config,
  }) => {
    const notificationsEnabled = config.notificationsEnabled();
    const onlineUsersEnabled = config.onlineUsersEnabled();
    const usePartySessionId = config.usePartySessionId ?? (() => null);
    const usePartyWebSocketHook = config.usePartyWebSocket ?? (() => undefined);
    const partySessionId = usePartySessionId() ?? '';

    usePartyWebSocketHook({
      sessionId: partySessionId,
      pageContext: config.partyPageContext ?? 'other',
    });

    const [notifications, setNotifications] = useState<NotificationMessage[]>([]);
    const [pingMessages, setPingMessages] = useState<PingToastMessage[]>([]);
    const notificationIdRef = useRef(0);
    const pingIdRef = useRef(0);
    const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
      if (!isAuthenticated || !onlineUsersEnabled) {
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
    }, [isAuthenticated, onlineUsersEnabled]);

    const startPollingOnlineUsers = useCallback(() => {
      if (pollingIntervalRef.current || !onlineUsersEnabled) return;

      setOnlineUsersError((prev) => prev ?? 'Using polling mode (WebSocket unavailable)');
      fetchOnlineUsers();
      pollingIntervalRef.current = setInterval(fetchOnlineUsers, 10000);
    }, [fetchOnlineUsers, onlineUsersEnabled]);

    const handleNotificationMessage = useCallback((event: MessageEvent) => {
      try {
        const data: NotificationStreamMessage | { type: 'ping'; join_url?: string; from_username: string; timestamp: string } =
          JSON.parse(event.data);

        if ('phrase_text' in data) {
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
      path: '/qf/notifications/ws',
      enabled: isAuthenticated && notificationsEnabled,
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
      [],
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
      [startPollingOnlineUsers, stopPollingOnlineUsers],
    );

    const handleOnlineUsersConnectError = useCallback(() => {
      setOnlineUsersConnected(false);
      startPollingOnlineUsers();
      return true;
    }, [startPollingOnlineUsers]);

    useWebSocket({
      path: '/qf/users/online/ws',
      enabled: isAuthenticated && onlineUsersEnabled,
      onOpen: handleOnlineUsersOpen,
      onMessage: handleOnlineUsersMessage,
      onError: handleOnlineUsersError,
      onClose: handleOnlineUsersClose,
      onConnectError: handleOnlineUsersConnectError,
    });

    useEffect(() => {
      if (!isAuthenticated || !onlineUsersEnabled) {
        stopPollingOnlineUsers();
        clearPingTimeouts();
        setOnlineUsers([]);
        setTotalCount(0);
        setPingStatus({});
        setOnlineUsersConnected(false);
        setOnlineUsersError(onlineUsersEnabled ? null : 'Online users are disabled');
        setLoadingOnlineUsers(false);
      }
    }, [
      isAuthenticated,
      stopPollingOnlineUsers,
      clearPingTimeouts,
      onlineUsersEnabled,
    ]);

    const addNotification = (message: NotificationMessage) => {
      setNotifications((prev) => [...prev, message]);
    };

    const removeNotification = (id: string) => {
      setNotifications((prev) => prev.filter((notification) => notification.id !== id));
    };

    const clearAll = () => {
      setNotifications([]);
      setPingMessages([]);
    };

    const handlePingUser = async (username: string) => {
      if (!username) return;

      setPingStatus((prev) => ({ ...prev, [username]: 'sending' }));

      try {
        const response = await apiClient.pingUser(username);
        if (!response.ok) {
          throw new Error('Failed to send ping');
        }

        setPingStatus((prev) => ({ ...prev, [username]: 'sent' }));

        const timeoutId = setTimeout(() => {
          setPingStatus((prev) => {
            const { [username]: _removed, ...rest } = prev;
            return rest;
          });
        }, 2000);

        pingResetTimeoutsRef.current.push(timeoutId);
      } catch (err) {
        console.error('Failed to send ping:', err);
        setPingStatus((prev) => ({ ...prev, [username]: 'idle' }));
      }
    };

    const removePingMessage = (id: string) => {
      setPingMessages((prev) => prev.filter((ping) => ping.id !== id));
    };

    const value: NotificationContextType = {
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
    };

    return (
      <NotificationContext.Provider value={value}>
        {children}
      </NotificationContext.Provider>
    );
  };

  const useNotifications = (): NotificationContextType => {
    const context = useContext(NotificationContext);
    if (!context) {
      throw new Error('useNotifications must be used within NotificationProvider');
    }
    return context;
  };

  return { NotificationProvider, useNotifications };
};
