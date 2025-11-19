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
  onSessionUpdate?: (data: any) => void;
}

export interface UsePartyWebSocketReturn {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  reconnect: () => void;
}

const WS_BASE_URL = import.meta.env.VITE_WS_URL ||
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
  const { sessionId, ...handlers } = options;

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(async () => {
    if (!state.isAuthenticated || !sessionId) {
      console.log('❌ Cannot connect WebSocket: not authenticated or no session ID');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('✅ WebSocket already connected');
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

          switch (message.type) {
            case 'phase_transition':
              handlers.onPhaseTransition?.(message.data as any);
              break;

            case 'player_joined':
              handlers.onPlayerJoined?.(message.data as any);
              break;

            case 'player_left':
              handlers.onPlayerLeft?.(message.data as any);
              break;

            case 'player_ready':
              handlers.onPlayerReady?.(message.data as any);
              break;

            case 'player_progress':
              handlers.onProgressUpdate?.(message.data as any);
              break;

            case 'session_started':
              handlers.onSessionStarted?.(message.data as any);
              break;

            default:
              // Handle other message types
              if (message.type === 'session_completed' || message.type === 'session_update') {
                handlers.onSessionUpdate?.(message.data);
              } else {
                console.warn('Unknown Party WebSocket message type:', message.type);
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

        // Attempt reconnection if not max attempts
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          setError('Maximum reconnection attempts reached');
        }
      };
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect');
      setConnecting(false);
    }
  }, [state.isAuthenticated, sessionId, handlers]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnected(false);
    setConnecting(false);
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
