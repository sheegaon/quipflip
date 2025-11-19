import { useEffect, useRef, useState, useCallback } from 'react';
import { useGame } from '../contexts/GameContext';
import apiClient from '../api/client';
import type { PartyWebSocketMessage } from '../api/types';

export interface UsePartyWebSocketOptions {
  sessionId: string;
  onPhaseTransition?: (data: { old_phase: string; new_phase: string; message: string }) => void;
  onPlayerJoined?: (data: { player_id: string; username: string; participant_count: number }) => void;
  onPlayerLeft?: (data: { player_id: string; username: string; participant_count: number }) => void;
  onPlayerReady?: (data: { player_id: string; username: string; ready_count: number; total_count: number }) => void;
  onProgressUpdate?: (data: {
    player_id: string;
    username: string;
    action: string;
    progress: { prompts_submitted: number; copies_submitted: number; votes_submitted: number };
    session_progress: { players_done_with_phase: number; total_players: number };
  }) => void;
  onSessionStarted?: (data: { current_phase: string; participant_count: number; message: string }) => void;
  onSessionCompleted?: (data: { completed_at: string; message: string }) => void;
  onSessionUpdate?: (data: Record<string, unknown>) => void;
  onHostPing?: (data: { host_player_id: string; host_username: string; join_url: string }) => void;
}

export interface UsePartyWebSocketReturn {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  reconnect: () => void;
}

const WS_BASE_URL = import.meta.env.VITE_BACKEND_WS_URL ||
  (window.location.protocol === 'https:' ? 'wss:' : 'ws:') +
  '//' + window.location.host.replace(':5173', ':8000');

/**
 * Hook for managing Party Mode WebSocket connection.
 * Provides real-time updates for party session events.
 */
export function usePartyWebSocket(
  options: UsePartyWebSocketOptions
): UsePartyWebSocketReturn {
  const { state } = useGame();
  const { sessionId } = options;

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const isRateLimitedRef = useRef(false);
  const rateLimitCooldownRef = useRef<NodeJS.Timeout | null>(null);

  // Store handlers in a ref to prevent reconnection on every render
  // The ref is updated on every render but doesn't trigger the connect callback
  const handlersRef = useRef(options);
  handlersRef.current = options;

  const connect = useCallback(async () => {
    if (!state.isAuthenticated || !sessionId) {
      console.log('❌ Cannot connect WebSocket: not authenticated or no session ID');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('✅ WebSocket already connected');
      return;
    }

    // Don't attempt connection if we're rate-limited
    if (isRateLimitedRef.current) {
      console.log('⏸️ WebSocket connection paused due to rate limiting');
      return;
    }

    setConnecting(true);
    setError(null);

    try {
      // Get WebSocket authentication token
      const { token } = await apiClient.getWebsocketToken();

      // Construct WebSocket URL
      const wsUrl = `${WS_BASE_URL}/qf/party/${sessionId}/ws?token=${token}`;

      console.log('🔌 Connecting to Party WebSocket:', wsUrl);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ Party WebSocket connected');
        setConnected(true);
        setConnecting(false);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const message: PartyWebSocketMessage = JSON.parse(event.data);
          console.log('📨 Party WebSocket message:', message);

          // WebSocket messages may include their payload in a nested "data" field or at the top level.
          const getPayload = <T extends Record<string, unknown>>(fallback: PartyWebSocketMessage) => {
            const candidate = (message as { data?: Record<string, unknown> }).data;
            return (candidate ?? fallback) as T;
          };

          switch (message.type) {
            case 'phase_transition':
              handlersRef.current.onPhaseTransition?.(getPayload(message));
              break;

            case 'player_joined':
              handlersRef.current.onPlayerJoined?.(getPayload(message));
              break;

            case 'player_left':
              handlersRef.current.onPlayerLeft?.(getPayload(message));
              break;

            case 'player_ready':
              handlersRef.current.onPlayerReady?.(getPayload(message));
              break;

            case 'player_progress':
              handlersRef.current.onProgressUpdate?.(getPayload(message));
              break;

            case 'session_started':
              handlersRef.current.onSessionStarted?.(getPayload(message));
              break;

            case 'session_completed':
              handlersRef.current.onSessionCompleted?.(getPayload(message));
              break;

            case 'session_update':
              handlersRef.current.onSessionUpdate?.(getPayload(message));
              break;

            case 'host_ping':
              handlersRef.current.onHostPing?.(getPayload(message));
              break;

            default: {
              // Exhaustiveness check - TypeScript will error if we miss a case
              const _exhaustiveCheck: never = message;
              console.warn('Unknown Party WebSocket message type:', _exhaustiveCheck);
              break;
            }
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('❌ Party WebSocket error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log('🔌 Party WebSocket disconnected');
        setConnected(false);
        setConnecting(false);
        wsRef.current = null;

        // Attempt reconnection if not max attempts and not rate limited
        if (reconnectAttemptsRef.current < maxReconnectAttempts && !isRateLimitedRef.current) {
          // Start with 5 second delay, then exponential backoff up to 60 seconds
          const delay = Math.min(5000 * Math.pow(2, reconnectAttemptsRef.current), 60000);
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else if (isRateLimitedRef.current) {
          console.log('⏸️ Reconnection paused due to rate limiting');
        } else {
          setError('Maximum reconnection attempts reached');
        }
      };
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to connect';

      // Check if this is a rate limit error
      if (errorMessage.includes('429') || errorMessage.includes('Rate limit')) {
        console.log('⏸️ Rate limited - pausing reconnection for 60 seconds');
        isRateLimitedRef.current = true;
        setError('Rate limited. Retrying in 60 seconds...');

        // Clear rate limit flag after 60 seconds
        if (rateLimitCooldownRef.current) {
          clearTimeout(rateLimitCooldownRef.current);
        }
        rateLimitCooldownRef.current = setTimeout(() => {
          console.log('✅ Rate limit cooldown complete');
          isRateLimitedRef.current = false;
          reconnectAttemptsRef.current = 0; // Reset attempts after cooldown
          setError(null);
        }, 60000);
      } else {
        setError(errorMessage);
      }

      setConnecting(false);
    }
  }, [state.isAuthenticated, sessionId]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (rateLimitCooldownRef.current) {
      clearTimeout(rateLimitCooldownRef.current);
      rateLimitCooldownRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnected(false);
    setConnecting(false);
    isRateLimitedRef.current = false;
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect, disconnect]);

  // Auto-connect when authenticated and session ID is available
  useEffect(() => {
    if (state.isAuthenticated && sessionId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [state.isAuthenticated, sessionId, connect, disconnect]);

  return {
    connected,
    connecting,
    error,
    reconnect,
  };
}
