import { MutableRefObject, useCallback, useEffect, useMemo, useRef } from 'react';
import apiClient from '@/api/client';

type ListenerRef = MutableRefObject<UseWebSocketOptions>;

interface UseWebSocketOptions {
  path: string;
  enabled: boolean;
  onBeforeConnect?: () => void;
  onOpen?: (socket: WebSocket) => void;
  onMessage?: (event: MessageEvent) => void;
  onError?: (event: Event, socket: WebSocket) => void;
  onClose?: (event: CloseEvent) => boolean | void;
  onConnectError?: (error: unknown) => boolean | void;
}

interface Listener {
  id: symbol;
  ref: ListenerRef;
  enabled: boolean;
}

interface BackoffController {
  schedule: (callback: () => void) => void;
  clear: () => void;
  reset: () => void;
}

interface ConnectionEntry {
  socket: WebSocket | null;
  listeners: Set<Listener>;
  backoff: BackoffController;
  isConnecting: boolean;
  tokenAbortController: AbortController | null;
}

const createBackoff = (baseDelay = 2000, maxDelay = 30000): BackoffController => {
  let attempts = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const clear = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  const reset = () => {
    attempts = 0;
    clear();
  };

  const schedule = (callback: () => void) => {
    clear();
    const delay = Math.min(maxDelay, baseDelay * Math.pow(2, attempts));
    attempts += 1;
    timeoutId = setTimeout(callback, delay);
  };

  return { schedule, clear, reset };
};

const buildWebSocketUrl = async (path: string, signal?: AbortSignal) => {
  const { token } = await apiClient.getWebsocketToken(signal);
  const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
  const backendWsUrl = import.meta.env.VITE_BACKEND_WS_URL || 'wss://quipflip-c196034288cd.herokuapp.com';

  const base = apiUrl.startsWith('/')
    ? `${backendWsUrl}${path}`
    : apiUrl.replace('http://', 'ws://').replace('https://', 'wss://') + path;

  const url = new URL(base, window.location.href);
  url.searchParams.set('token', token);

  return url.toString();
};

const connections = new Map<string, ConnectionEntry>();

const isAbortError = (error: unknown) => {
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  if (error instanceof Error && error.name === 'CanceledError') return true;
  return (error as { code?: string }).code === 'ERR_CANCELED';
};

const getConnection = (path: string): ConnectionEntry => {
  const existing = connections.get(path);
  if (existing) return existing;

  const entry: ConnectionEntry = {
    socket: null,
    listeners: new Set(),
    backoff: createBackoff(),
    isConnecting: false,
    tokenAbortController: null,
  };

  connections.set(path, entry);
  return entry;
};

const hasEnabledListeners = (entry: ConnectionEntry) => {
  for (const listener of entry.listeners) {
    if (listener.enabled) return true;
  }
  return false;
};

const notify = (
  entry: ConnectionEntry,
  event: keyof UseWebSocketOptions,
  ...args: unknown[]
) => {
  entry.listeners.forEach((listener) => {
    if (!listener.enabled) return;
    const handler = listener.ref.current[event];
    if (typeof handler === 'function') {
      (handler as (...args: unknown[]) => unknown)(...args);
    }
  });
};

const shouldReconnectAfter = (
  entry: ConnectionEntry,
  event: 'onClose' | 'onConnectError',
  payload: CloseEvent | unknown
) => {
  let shouldReconnect = false;
  let hasListener = false;

  entry.listeners.forEach((listener) => {
    if (!listener.enabled) return;
    hasListener = true;

    const handler = listener.ref.current[event];
    if (!handler) {
      shouldReconnect = true;
      return;
    }

    const result = handler(payload as never);
    if (result !== false) {
      shouldReconnect = true;
    }
  });

  return hasListener ? shouldReconnect : false;
};

const connect = async (path: string, entry: ConnectionEntry) => {
  if (entry.isConnecting || entry.socket || !hasEnabledListeners(entry)) return;

  entry.isConnecting = true;
  entry.tokenAbortController?.abort();
  entry.tokenAbortController = new AbortController();

  notify(entry, 'onBeforeConnect');

  try {
    const wsUrl = await buildWebSocketUrl(path, entry.tokenAbortController.signal);

    if (!hasEnabledListeners(entry)) {
      entry.isConnecting = false;
      entry.tokenAbortController?.abort();
      entry.tokenAbortController = null;
      return;
    }

    entry.tokenAbortController = null;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      entry.socket = socket;
      entry.isConnecting = false;
      entry.backoff.reset();
      notify(entry, 'onOpen', socket);
    };

    socket.onmessage = (event) => {
      notify(entry, 'onMessage', event);
    };

    socket.onerror = (event) => {
      notify(entry, 'onError', event, socket);
    };

    socket.onclose = (event) => {
      entry.socket = null;
      entry.isConnecting = false;

      if (!hasEnabledListeners(entry)) return;

      const shouldReconnect = shouldReconnectAfter(entry, 'onClose', event);

      if (shouldReconnect) {
        entry.backoff.schedule(() => connect(path, entry));
      }
    };
  } catch (err) {
    entry.socket = null;
    entry.isConnecting = false;
    entry.tokenAbortController = null;

    if (!hasEnabledListeners(entry)) return;

    if (isAbortError(err)) {
      return;
    }

    const shouldReconnect = shouldReconnectAfter(entry, 'onConnectError', err);

    if (shouldReconnect) {
      entry.backoff.schedule(() => connect(path, entry));
    }
  }
};

const syncConnection = (path: string, entry: ConnectionEntry) => {
  if (!hasEnabledListeners(entry)) {
    entry.backoff.clear();
    entry.backoff.reset();
    entry.isConnecting = false;
    entry.tokenAbortController?.abort();
    entry.tokenAbortController = null;
    if (entry.socket) {
      entry.socket.close();
      entry.socket = null;
    }
    return;
  }

  connect(path, entry);
};

const useWebSocket = (options: UseWebSocketOptions) => {
  const { path, enabled } = options;
  const listenerRef = useRef(options);

  useEffect(() => {
    listenerRef.current = options;
  }, [options]);

  const normalizedPath = useMemo(() => path, [path]);

  const forceReconnect = useCallback(() => {
    const entry = normalizedPath ? connections.get(normalizedPath) : null;
    if (!entry) return;

    entry.backoff.reset();

    if (entry.socket) {
      entry.socket.close();
      entry.socket = null;
    }

    entry.isConnecting = false;
    if (hasEnabledListeners(entry)) {
      entry.backoff.schedule(() => connect(normalizedPath, entry));
    }
  }, [normalizedPath]);

  useEffect(() => {
    if (!normalizedPath) return undefined;

    const entry = getConnection(normalizedPath);
    const listener: Listener = { id: Symbol(normalizedPath), ref: listenerRef, enabled };
    entry.listeners.add(listener);

    syncConnection(normalizedPath, entry);

    return () => {
      entry.listeners.delete(listener);
      syncConnection(normalizedPath, entry);
    };
  }, [enabled, normalizedPath]);

  const entry = normalizedPath ? connections.get(normalizedPath) : null;

  return { websocket: entry?.socket ?? null, reconnect: forceReconnect };
};

export default useWebSocket;
