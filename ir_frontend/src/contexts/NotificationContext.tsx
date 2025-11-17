import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
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

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: FC<NotificationProviderProps> = ({ children }) => {
  const [notifications, setNotifications] = useState<NotificationMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const notificationIdRef = useRef(0);
  const { isAuthenticated } = useIRGame();

  useEffect(() => {
    let wsAttempted = false;

    const connectWebSocket = async () => {
      if (wsAttempted) return;
      wsAttempted = true;

      try {
        const apiBase =
          import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000/ir`;
        const baseUrl = apiBase.startsWith('http')
          ? apiBase
          : `${window.location.origin}${apiBase}`;

        const tokenUrl = new URL('/auth/ws-token', baseUrl.replace(/\/$/, '') + '/');
        const tokenResponse = await fetch(tokenUrl.toString(), {
          credentials: 'include',
        });

        if (!tokenResponse.ok) {
          throw new Error('Failed to get WebSocket token');
        }

        const { token } = await tokenResponse.json();

        const wsUrl = new URL('/notifications/ws', baseUrl.replace(/\/$/, '') + '/');
        wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');
        wsUrl.searchParams.set('token', token);

        const ws = new WebSocket(wsUrl.toString());

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
            console.error('Failed to parse notification message:', err);
          }
        };

        ws.onerror = () => {
          console.debug('WebSocket error, connection failed silently');
        };

        ws.onclose = () => {
          console.debug('WebSocket disconnected, no reconnect');
        };

        wsRef.current = ws;
      } catch (err) {
        console.debug('WebSocket connection failed silently:', err);
      }
    };

    if (isAuthenticated) {
      connectWebSocket();
    }

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
    throw new Error('useNotifications must be used within NotificationProvider');
  }
  return context;
};
