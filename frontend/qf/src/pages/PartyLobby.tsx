import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '@crowdcraft/api/client.ts';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CircleIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import { BotIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { SoundOnIcon, SoundOffIcon, BellIcon } from '@crowdcraft/components/icons/SoundIcons.tsx';
import { quipflipBranding } from '@crowdcraft/utils/brandedMessages.ts';
import { playSound, primeAudio } from '@crowdcraft/utils/sound.ts';
import { useSoundSettings } from '@crowdcraft/hooks/useSoundSettings.ts';
import {
  getNotificationPermission,
  requestNotificationPermission,
  showBrowserNotification,
  type NotificationPermissionState,
} from '@crowdcraft/utils/browserNotifications.ts';
import { PartyStartTransition } from '../components/party/PartyStartTransition';
import type { QFPartySessionStatusResponse, QFPartyParticipant } from '@crowdcraft/api/types.ts';

const { loadingMessages } = quipflipBranding;

type ActivityKind = 'join' | 'leave' | 'ready' | 'ping' | 'info';

interface ActivityEntry {
  id: string;
  kind: ActivityKind;
  message: string;
  at: number;
}

const ACTIVITY_LIMIT = 15;

const ACTIVITY_DOT: Record<ActivityKind, string> = {
  join: 'bg-ccl-turquoise',
  leave: 'bg-gray-400',
  ready: 'bg-ccl-orange',
  ping: 'bg-ccl-navy',
  info: 'bg-ccl-teal',
};

const formatRelative = (at: number): string => {
  const secs = Math.max(0, Math.floor((Date.now() - at) / 1000));
  if (secs < 5) return 'just now';
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ago`;
};

/**
 * Party Lobby page - Players wait here until host starts the game
 */
export const PartyLobby: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();

  const [sessionStatus, setSessionStatus] = useState<QFPartySessionStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [isAddingAI, setIsAddingAI] = useState(false);
  const [isPinging, setIsPinging] = useState(false);

  // Activity tracking + sound / notification preferences
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const { muted, toggleMuted } = useSoundSettings();
  const [notifPermission, setNotifPermission] = useState<NotificationPermissionState>(
    getNotificationPermission()
  );
  const [, setRelativeTick] = useState(0);

  // Transition to game
  const [isTransitioning, setIsTransitioning] = useState(false);
  const transitionStartedRef = useRef(false);
  const loadSessionRequestIdRef = useRef(0);

  // Snapshot of participants from the previous status load, used to diff joins /
  // leaves / ready changes so activity tracking works over WebSocket *or* polling.
  const participantsRef = useRef<Map<string, QFPartyParticipant> | null>(null);

  // Check if current player is host
  const isHost = sessionStatus?.participants.find(p => p.player_id === player?.player_id)?.is_host ?? false;

  // Participant breakdowns
  const participants = sessionStatus?.participants ?? [];
  const totalCount = participants.length;
  const minPlayers = sessionStatus?.min_players ?? 6;
  const maxPlayers = sessionStatus?.max_players ?? 9;
  const humanParticipants = participants.filter(p => !p.is_ai);
  const humanReadyCount = humanParticipants.filter(p => p.status === 'READY').length;
  const humanNotReady = humanParticipants.filter(p => p.status !== 'READY');
  const allHumansReady = humanNotReady.length === 0;
  const hasEnoughPlayers = totalCount >= minPlayers;
  const neededAi = Math.max(0, minPlayers - totalCount);
  const availableSlots = Math.max(0, maxPlayers - totalCount);
  const needsAutoAiStart = isHost && allHumansReady && !hasEnoughPlayers;
  // Once the room has enough players, let the host nudge anyone who hasn't readied up.
  const inactiveHumans = hasEnoughPlayers ? humanNotReady.length : 0;
  const canPing = humanParticipants.length > 1;

  const pushActivity = useCallback((kind: ActivityKind, message: string) => {
    setActivity((prev) => [
      { id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, kind, message, at: Date.now() },
      ...prev,
    ].slice(0, ACTIVITY_LIMIT));
  }, []);

  // Diff the participant list against the previous snapshot and emit activity,
  // sounds, and background notifications for anything that changed.
  const reconcileActivity = useCallback((next: QFPartyParticipant[]) => {
    const prev = participantsRef.current;
    const nextMap = new Map(next.map((p) => [p.participant_id, p]));

    // First load seeds the snapshot silently so we don't announce existing players.
    if (prev === null) {
      participantsRef.current = nextMap;
      return;
    }

    const selfId = player?.player_id;

    // Joins
    for (const p of next) {
      if (prev.has(p.participant_id) || p.player_id === selfId) continue;
      if (p.is_ai) {
        pushActivity('join', `${p.username} (AI) joined`);
      } else {
        pushActivity('join', `${p.username} joined`);
        playSound('join');
        showBrowserNotification('Someone joined your party', {
          body: `${p.username} is in the lobby`,
          tag: 'qf-party-activity',
        });
      }
    }

    // Leaves
    for (const [id, p] of prev) {
      if (nextMap.has(id) || p.player_id === selfId) continue;
      if (p.is_ai) {
        pushActivity('leave', `${p.username} (AI) left`);
      } else {
        pushActivity('leave', `${p.username} left`);
        playSound('leave');
        showBrowserNotification('Someone left your party', {
          body: `${p.username} left the lobby`,
          tag: 'qf-party-activity',
        });
      }
    }

    // Ready transitions (not ready -> ready)
    for (const p of next) {
      const before = prev.get(p.participant_id);
      if (before && before.status !== 'READY' && p.status === 'READY' && !p.is_ai) {
        pushActivity('ready', `${p.username} is ready`);
        if (p.player_id !== selfId) playSound('ready');
      }
    }

    participantsRef.current = nextMap;
  }, [player?.player_id, pushActivity]);

  const beginStartTransition = useCallback(() => {
    if (transitionStartedRef.current) return;
    transitionStartedRef.current = true;
    setIsTransitioning(true);
  }, []);

  const handleTransitionComplete = useCallback(() => {
    if (!sessionId) return;
    navigate(`/party/game/${sessionId}`);
  }, [navigate, sessionId]);

  // Load session status
  const loadSessionStatus = useCallback(async () => {
    if (!sessionId) return;

    const requestId = ++loadSessionRequestIdRef.current;

    try {
      const status = await apiClient.qfGetPartySessionStatus(sessionId);
      if (requestId !== loadSessionRequestIdRef.current) return;
      setSessionStatus(status);
      reconcileActivity(status.participants);

      // If the session has progressed past the lobby, navigate to the correct screen via REST status
      if (status.current_phase === 'RESULTS' || status.status === 'COMPLETED') {
        navigate(`/party/results/${sessionId}`);
        return;
      }

      if (status.status === 'IN_PROGRESS' || status.current_phase !== 'LOBBY') {
        // Show the celebratory hand-off; it navigates into the game when done.
        beginStartTransition();
      }
    } catch (err) {
      if (requestId === loadSessionRequestIdRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to load session');
      }
    } finally {
      if (requestId === loadSessionRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [beginStartTransition, navigate, reconcileActivity, sessionId]);

  const refreshSessionStatus = useCallback(() => {
    void loadSessionStatus();
  }, [loadSessionStatus]);

  const handleSessionStarted = useCallback(() => {
    // Start the transition immediately; REST polling keeps the count current.
    beginStartTransition();
    refreshSessionStatus();
  }, [beginStartTransition, refreshSessionStatus]);

  const handleHostPing = useCallback((data: { host_player_id: string; host_username: string; join_url: string }) => {
    // The host's own broadcast echoes back - ignore it.
    if (data.host_player_id === player?.player_id) return;
    pushActivity('ping', `${data.host_username} pinged the lobby`);
    // The audible ping is played once by the global notification handler so a
    // player who has wandered off still hears it; here we add a feed entry and
    // a background notification for the lobby view.
    showBrowserNotification('Party ping', {
      body: `${data.host_username} is waiting for everyone to ready up`,
      tag: 'qf-party-ping',
    });
  }, [player?.player_id, pushActivity]);

  const handleSessionUpdate = useCallback((data: Record<string, unknown>) => {
    // Show host change notification
    if (data.reason === 'inactive_player_removed' && typeof data.message === 'string') {
      setNotification(data.message);
      pushActivity('info', data.message);
      setTimeout(() => setNotification(null), 5000); // Clear after 5 seconds
    }
    refreshSessionStatus();
  }, [pushActivity, refreshSessionStatus]);

  const partyWebSocketConfig = useMemo(() => ({
    sessionId: sessionId ?? '',
    pageContext: 'lobby' as const,
    onPlayerJoined: refreshSessionStatus,
    onPlayerLeft: refreshSessionStatus,
    onPlayerReady: refreshSessionStatus,
    onSessionStarted: handleSessionStarted,
    onHostPing: handleHostPing,
    onSessionUpdate: handleSessionUpdate,
  }), [
    handleHostPing,
    handleSessionStarted,
    handleSessionUpdate,
    refreshSessionStatus,
    sessionId,
  ]);

  useEffect(() => {
    loadSessionStatus();
  }, [loadSessionStatus]);

  // Poll for session changes so gameplay progresses via REST even without WebSocket
  useEffect(() => {
    if (!sessionId) return undefined;

    let timeoutId: number | null = null;
    let cancelled = false;

    const poll = async () => {
      await loadSessionStatus();
      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 5000);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [loadSessionStatus, sessionId]);

  // Keep relative timestamps in the activity feed fresh.
  useEffect(() => {
    const id = window.setInterval(() => setRelativeTick((t) => t + 1), 10000);
    return () => window.clearInterval(id);
  }, []);

  // Resume the audio context on the first user gesture so cues are audible.
  useEffect(() => {
    const prime = () => primeAudio();
    window.addEventListener('pointerdown', prime, { once: true });
    window.addEventListener('keydown', prime, { once: true });
    return () => {
      window.removeEventListener('pointerdown', prime);
      window.removeEventListener('keydown', prime);
    };
  }, []);

  // WebSocket handlers - these nudge an immediate reload; reconcileActivity (run
  // inside loadSessionStatus) is the single source of truth for sounds/feed.
  const {
    connected: wsConnected,
    connecting: wsConnecting,
  } = usePartyWebSocket(partyWebSocketConfig);

  const handleStartParty = async () => {
    if (!sessionId || !isHost || isStarting || !allHumansReady) return;

    primeAudio();
    setIsStarting(true);
    try {
      if (!hasEnoughPlayers) {
        if (neededAi > availableSlots) {
          throw new Error('Not enough open slots to add AI players.');
        }

        for (let i = 0; i < neededAi; i += 1) {
          await apiClient.qfAddAIPlayerToParty(sessionId);
        }
        await loadSessionStatus();
      }

      await apiClient.qfStartPartySession(sessionId);
      await loadSessionStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start party');
      setIsStarting(false);
    } finally {
      setIsStarting(false);
    }
  };

  const handleLeave = async () => {
    if (!sessionId) return;

    try {
      await apiClient.qfLeavePartySession(sessionId);
      navigate('/party');
    } catch (err) {
      console.error('Failed to leave party:', err);
      navigate('/party');
    }
  };

  const handleAddAI = async () => {
    if (!sessionId) return;

    setIsAddingAI(true);
    try {
      await apiClient.qfAddAIPlayerToParty(sessionId);
      // Reload session status to show new AI player
      await loadSessionStatus();
      setNotification('AI player added to the party!');
      setTimeout(() => setNotification(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add AI player');
      setTimeout(() => setError(null), 3000);
    } finally {
      setIsAddingAI(false);
    }
  };

  const handlePingPlayers = async () => {
    if (!sessionId || !isHost) return;

    primeAudio();
    setIsPinging(true);
    try {
      await apiClient.qfPingParty(sessionId);
      const message = inactiveHumans > 0
        ? `Pinged ${inactiveHumans} player${inactiveHumans === 1 ? '' : 's'} who aren't ready yet.`
        : 'Ping sent to everyone in your party.';
      setNotification(message);
      pushActivity('ping', 'You pinged the lobby');
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ping players');
      setTimeout(() => setError(null), 4000);
    } finally {
      setIsPinging(false);
    }
  };

  const handleEnableNotifications = async () => {
    primeAudio();
    const result = await requestNotificationPermission();
    setNotifPermission(result);
    if (result === 'granted') {
      setNotification('Browser alerts enabled. We’ll let you know when players come and go.');
      setTimeout(() => setNotification(null), 4000);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
      </div>
    );
  }

  if (error || !sessionStatus) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-turquoise flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-md w-full tile-card p-8 slide-up-enter text-center space-y-4">
          <div className="flex justify-center mb-4">
            <CircleIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-2">Session Not Found</h2>
          <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
            <p className="text-sm text-red-800">{error || 'Session not found'}</p>
          </div>
          <button
            onClick={() => navigate('/party')}
            className="w-full bg-ccl-navy hover:bg-ccl-teal text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            Back to Party Mode
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-turquoise flex items-center justify-center p-4 bg-pattern">
      {isTransitioning && (
        <PartyStartTransition playerCount={totalCount} onComplete={handleTransitionComplete} />
      )}
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        {/* Header */}
        <div className="relative text-center mb-8">
          {/* Sound toggle */}
          <button
            type="button"
            onClick={() => { primeAudio(); toggleMuted(); }}
            aria-pressed={muted}
            title={muted ? 'Sounds are off — click to turn on' : 'Sounds are on — click to mute'}
            className="absolute right-0 top-0 flex items-center gap-1.5 px-3 py-2 rounded-tile border-2 border-ccl-navy/15 text-ccl-navy hover:border-ccl-navy/40 transition-colors"
          >
            {muted ? <SoundOffIcon className="w-5 h-5 text-gray-500" /> : <SoundOnIcon className="w-5 h-5 text-ccl-teal" />}
            <span className="text-xs font-semibold hidden sm:inline">{muted ? 'Muted' : 'Sound'}</span>
          </button>

          <div className="flex items-center justify-center gap-2 mb-2">
            <CircleIcon className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-ccl-navy">Party Lobby</h1>
          </div>
          <p className="text-ccl-teal">Players join first, then mark ready when they’re set.</p>
        </div>

        <div className="space-y-6">
          {/* Notification Display */}
          {notification && (
            <div className="space-y-3">
              <div className="bg-ccl-turquoise bg-opacity-10 border-2 border-ccl-turquoise rounded-tile p-4 text-center">
                <p className="text-ccl-navy font-semibold">{notification}</p>
              </div>
            </div>
          )}

          {/* Party Code Display */}
          <div className="tile-card shadow-tile p-6 text-center bg-ccl-orange bg-opacity-5 border-2 border-ccl-orange">
            <h2 className="text-sm font-semibold text-ccl-teal uppercase mb-2">Party Code</h2>
            <div
              className="text-5xl font-bold font-mono text-ccl-orange-deep tracking-widest"
            >
              {sessionStatus.party_code}
            </div>
            <p className="text-sm text-ccl-teal mt-2">Share this code with friends to join.</p>
          </div>

          {/* Session Info */}
          <div className="tile-card shadow-tile-sm p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-ccl-teal">Humans Ready</p>
                <p className="text-2xl font-display font-bold text-ccl-navy">
                  {humanReadyCount} / {humanParticipants.length}
                </p>
              </div>
              <div>
                <p className="text-sm text-ccl-teal">Total Players</p>
                <p className="text-2xl font-display font-bold text-ccl-navy">
                  {totalCount} / {maxPlayers}
                </p>
              </div>
              <div>
                <p className="text-sm text-ccl-teal">Minimum to Start</p>
                <p className="text-2xl font-display font-bold text-ccl-navy">{minPlayers}</p>
              </div>
            </div>
            {!hasEnoughPlayers && (
              <p className="text-xs text-ccl-teal mt-2">
                Need {neededAi} more player{neededAi === 1 ? '' : 's'} before starting.
              </p>
            )}
          </div>

          {/* Player List */}
          <div className="tile-card shadow-tile p-4">
            <h3 className="text-lg font-display font-bold text-ccl-navy mb-4">Players</h3>
            <div className="space-y-2">
              {participants.map((participant: QFPartyParticipant) => (
                <div
                  key={participant.participant_id}
                  className="flex items-center justify-between p-3 bg-ccl-cream rounded-tile"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        participant.status === 'READY'
                          ? 'bg-ccl-turquoise'
                          : 'bg-gray-300'
                      }`}
                      title={participant.status === 'READY' ? 'Ready' : 'Not ready'}
                    />
                    <span className="font-semibold text-ccl-navy flex items-center gap-2">
                      {participant.username}
                      {participant.is_ai && <BotIcon className="w-4 h-4" />}
                    </span>
                    {participant.is_host && (
                      <span className="px-2 py-1 text-xs font-semibold text-ccl-orange-deep bg-ccl-orange bg-opacity-20 rounded-tile">
                        HOST
                      </span>
                    )}
                    {participant.player_id === player?.player_id && (
                      <span className="px-2 py-1 text-xs font-semibold text-ccl-turquoise bg-ccl-turquoise bg-opacity-20 rounded-tile">
                        YOU
                      </span>
                    )}
                  </div>
                  <span className={`text-sm font-semibold ${
                    participant.status === 'READY' ? 'text-ccl-turquoise' : 'text-gray-500'
                  }`}>
                    {participant.status === 'READY' ? 'Ready' : 'Waiting...'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Activity Feed */}
          <div className="tile-card shadow-tile p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-display font-bold text-ccl-navy">Lobby Activity</h3>
              <span className="flex items-center gap-1.5 text-xs font-semibold text-ccl-teal">
                <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-ccl-turquoise animate-pulse' : 'bg-gray-300'}`} />
                Live
              </span>
            </div>
            {activity.length === 0 ? (
              <p className="text-sm text-ccl-teal">
                Waiting for players… joins, exits, and ready-ups will show up here.
              </p>
            ) : (
              <ul className="space-y-2 max-h-44 overflow-y-auto pr-1">
                {activity.map((entry) => (
                  <li key={entry.id} className="flex items-center gap-3 text-sm">
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${ACTIVITY_DOT[entry.kind]}`} />
                    <span className="text-ccl-navy flex-1">{entry.message}</span>
                    <span className="text-xs text-gray-400 flex-shrink-0">{formatRelative(entry.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Browser notification opt-in */}
          {notifPermission === 'default' && (
            <button
              type="button"
              onClick={handleEnableNotifications}
              className="w-full flex items-center justify-center gap-2 text-sm font-semibold text-ccl-teal hover:text-ccl-turquoise border-2 border-dashed border-ccl-teal/30 hover:border-ccl-turquoise rounded-tile py-2.5 transition-colors"
            >
              <BellIcon className="w-4 h-4" />
              Get a browser alert when players join or leave
            </button>
          )}

          {/* Action Buttons */}
          <div className="space-y-3">
            {/* Ping Button (host only) */}
            {isHost && (
              <button
                onClick={handlePingPlayers}
                disabled={isPinging || !canPing}
                className={`w-full flex items-center justify-center gap-2 font-semibold py-3 px-4 rounded-tile transition-all disabled:opacity-60 disabled:cursor-not-allowed ${
                  inactiveHumans > 0
                    ? 'bg-ccl-navy text-white hover:bg-ccl-teal'
                    : 'border-2 border-ccl-navy text-ccl-navy bg-white hover:bg-ccl-navy hover:text-white'
                }`}
              >
                <BellIcon className="w-5 h-5" />
                {isPinging
                  ? 'Pinging players...'
                  : inactiveHumans > 0
                    ? `Ping ${inactiveHumans} inactive player${inactiveHumans === 1 ? '' : 's'}`
                    : 'Ping Everyone'}
              </button>
            )}
            {isHost && inactiveHumans > 0 && (
              <p className="text-xs text-center text-ccl-teal -mt-1">
                Sends an audible nudge to players who haven’t readied up.
              </p>
            )}

            {/* Add AI Player Button (host only) */}
            {isHost && totalCount < maxPlayers && (
              <button
                onClick={handleAddAI}
                disabled={isAddingAI}
                className="w-full bg-ccl-teal hover:bg-ccl-turquoise text-white font-semibold py-3 px-4 rounded-tile transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAddingAI ? 'Adding AI Player...' : '+ Add AI Player'}
              </button>
            )}

            {/* Start Button (host only) */}
            {isHost && (
              <button
                onClick={handleStartParty}
                disabled={!allHumansReady || isStarting}
                className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
                  allHumansReady && !isStarting
                    ? 'bg-ccl-orange hover:bg-ccl-orange-deep text-white hover:shadow-tile-sm'
                    : 'bg-gray-400 text-white cursor-not-allowed'
                }`}
              >
                {isStarting
                  ? 'Starting...'
                  : needsAutoAiStart
                    ? (
                      <span className="flex items-center justify-center gap-2">
                        Start Party With <BotIcon className="w-5 h-5" /> AI
                      </span>
                    )
                    : 'Start Party'}
              </button>
            )}

            {isHost && !allHumansReady && (
              <p className="text-sm text-center text-ccl-teal">
                Waiting for {humanNotReady.length} human player{humanNotReady.length === 1 ? '' : 's'} to return to the lobby.
              </p>
            )}
            {isHost && needsAutoAiStart && (
              <p className="text-sm text-center text-ccl-teal">
                All humans are ready! We'll add {neededAi} AI teammate{neededAi === 1 ? '' : 's'} and start immediately.
              </p>
            )}
            {isHost && !hasEnoughPlayers && !needsAutoAiStart && allHumansReady && (
              <p className="text-sm text-center text-ccl-teal">
                Need at least {minPlayers} total players to start.
              </p>
            )}

            {/* Leave Button */}
            <button
              onClick={handleLeave}
              className="w-full border-2 border-ccl-navy bg-white hover:bg-ccl-navy hover:text-white text-ccl-navy font-semibold py-3 px-4 rounded-tile transition-all"
            >
              Leave Party
            </button>
          </div>

          {/* Back to Dashboard Button */}
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full mt-4 flex items-center justify-center gap-2 text-ccl-teal hover:text-ccl-turquoise py-2 font-medium transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span>Back to Dashboard</span>
          </button>

          {/* Connection Status */}
          <div className="mt-6 p-4 bg-ccl-navy bg-opacity-5 rounded-tile">
            <p className="text-sm text-center text-ccl-teal">
              {wsConnecting && '🔄 Connecting to live updates...'}
              {wsConnected && '✅ Connected to live updates'}
              {!wsConnecting && !wsConnected && '⚠️ Not connected - updates may be delayed'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyLobby;
