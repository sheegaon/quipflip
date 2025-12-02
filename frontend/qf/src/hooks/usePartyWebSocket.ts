import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import useWebSocket from '@crowdcraft/hooks/useWebSocket';
import type {
  HostPingPayload,
  PartyWebSocketMessage,
  PhaseTransitionPayload,
  PlayerJoinedPayload,
  PlayerLeftPayload,
  PlayerReadyPayload,
  ProgressUpdatePayload,
  SessionCompletedPayload,
  SessionStartedPayload,
  SessionUpdatePayload,
} from '@crowdcraft/api/types.ts';

export interface UsePartyWebSocketOptions {
  sessionId: string;
  pageContext?: 'lobby' | 'game' | 'other';
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
  onSessionCompleted?: (data: { completed_at: string | null; message: string }) => void;
  onSessionUpdate?: (data: Record<string, unknown>) => void;
  onHostPing?: (data: { host_player_id: string; host_username: string; join_url: string }) => void;
}

export interface UsePartyWebSocketReturn {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  reconnect: () => void;
}

const parsePayload = <T extends PartyWebSocketMessage>(message: T) =>
  (message as { data?: unknown }).data ?? message;

export function usePartyWebSocket(
  options: UsePartyWebSocketOptions
): UsePartyWebSocketReturn {
  const { state } = useGame();
  const { sessionId, pageContext = 'other' } = options;

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlersRef = useRef(options);
  useEffect(() => {
    handlersRef.current = options;
  }, [options]);

  const enabled = state.isAuthenticated && Boolean(sessionId);
  const path = useMemo(
    () => (sessionId ? `/qf/party/${sessionId}/ws?context=${pageContext}` : ''),
    [pageContext, sessionId]
  );

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data) as PartyWebSocketMessage;

      switch (message.type) {
        case 'phase_transition':
          handlersRef.current.onPhaseTransition?.(parsePayload<PartyWebSocketMessage>(message) as PhaseTransitionPayload);
          break;
        case 'player_joined':
          handlersRef.current.onPlayerJoined?.(parsePayload<PartyWebSocketMessage>(message) as PlayerJoinedPayload);
          break;
        case 'player_left':
          handlersRef.current.onPlayerLeft?.(parsePayload<PartyWebSocketMessage>(message) as PlayerLeftPayload);
          break;
        case 'player_ready':
          handlersRef.current.onPlayerReady?.(parsePayload<PartyWebSocketMessage>(message) as PlayerReadyPayload);
          break;
        case 'progress_update':
          handlersRef.current.onProgressUpdate?.(parsePayload<PartyWebSocketMessage>(message) as ProgressUpdatePayload);
          break;
        case 'session_started':
          handlersRef.current.onSessionStarted?.(parsePayload<PartyWebSocketMessage>(message) as SessionStartedPayload);
          break;
        case 'session_completed':
          handlersRef.current.onSessionCompleted?.(parsePayload<PartyWebSocketMessage>(message) as SessionCompletedPayload);
          break;
        case 'session_update':
          handlersRef.current.onSessionUpdate?.(parsePayload<PartyWebSocketMessage>(message) as SessionUpdatePayload);
          break;
        case 'host_ping':
          handlersRef.current.onHostPing?.(parsePayload<PartyWebSocketMessage>(message) as HostPingPayload);
          break;
        default:
          console.warn('Unknown Party WebSocket message type:', message);
      }
    } catch (err) {
      console.error('Error parsing WebSocket message:', err);
    }
  }, []);

  const handleClose = useCallback(
    (event: CloseEvent) => {
      setConnected(false);
      setConnecting(false);

      const authCloseCodes = new Set([4000, 4001, 4002, 4003, 4401, 4403]);
      if (authCloseCodes.has(event.code)) {
        setError(event.reason || 'Session is no longer active or you were removed from the party. Please return to party mode.');
        return false;
      }

      return true;
    },
    []
  );

  const handleConnectError = useCallback((err: unknown) => {
    setConnecting(false);
    const message = err instanceof Error ? err.message : 'Failed to connect';

    if (message.includes('403') || message.includes('401') || message.includes('Unauthorized') || message.includes('Forbidden')) {
      setError('Session is no longer active or you were removed from the party. Please return to party mode.');
      return false;
    }

    if (message.includes('429') || message.includes('Rate limit')) {
      setError('Rate limited. Retrying...');
    } else {
      setError(message);
    }

    return true;
  }, []);

  const { reconnect } = useWebSocket({
    path,
    enabled,
    onBeforeConnect: () => {
      setConnecting(true);
      setError(null);
    },
    onOpen: () => {
      setConnected(true);
      setConnecting(false);
      setError(null);
    },
    onMessage: handleMessage,
    onError: () => {
      setError('WebSocket connection error');
    },
    onClose: handleClose,
    onConnectError: handleConnectError,
  });

  useEffect(() => {
    if (!enabled) {
      setConnected(false);
      setConnecting(false);
      setError(null);
    }
  }, [enabled]);

  return { connected, connecting, error, reconnect };
}
