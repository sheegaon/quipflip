import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { BotIcon } from '../components/icons/EngagementIcons';
import { loadingMessages } from '../utils/brandedMessages';
import type { PartySessionStatusResponse, PartyParticipant } from '../api/types';

/**
 * Party Lobby page - Players wait here until host starts the game
 */
export const PartyLobby: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();

  const [sessionStatus, setSessionStatus] = useState<PartySessionStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [isAddingAI, setIsAddingAI] = useState(false);
  const [isPinging, setIsPinging] = useState(false);

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

  // Load session status
  const loadSessionStatus = useCallback(async () => {
    if (!sessionId) return;

    try {
      const status = await apiClient.getPartySessionStatus(sessionId);
      setSessionStatus(status);

      // If session already started, navigate to game
      if (status.status === 'ACTIVE') {
        navigate(`/party/game/${sessionId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
    } finally {
      setLoading(false);
    }
  }, [navigate, sessionId]);

  useEffect(() => {
    loadSessionStatus();
  }, [loadSessionStatus]);

  // WebSocket handlers
  const {
    connected: wsConnected,
    connecting: wsConnecting,
  } = usePartyWebSocket({
    sessionId: sessionId ?? '',
    onPlayerJoined: (data) => {
      console.log(`${data.username} joined the party!`);
      loadSessionStatus(); // Reload to get updated participant list
    },
    onPlayerLeft: (data) => {
      console.log(`${data.username} left the party`);
      loadSessionStatus();
    },
    onPlayerReady: (data) => {
      console.log(`${data.username} is ready!`);
      loadSessionStatus();
    },
    onSessionStarted: (data) => {
      console.log('Party started!', data);
      // Navigate to game page
      navigate(`/party/game/${sessionId}`);
    },
    onSessionUpdate: (data) => {
      console.log('Session update:', data);
      // Show host change notification
      if (data.reason === 'inactive_player_removed' && typeof data.message === 'string') {
        setNotification(data.message);
        setTimeout(() => setNotification(null), 5000); // Clear after 5 seconds
      }
      loadSessionStatus();
    },
  });

  const handleStartParty = async () => {
    if (!sessionId || !isHost || isStarting || !allHumansReady) return;

    setIsStarting(true);
    try {
      if (!hasEnoughPlayers) {
        if (neededAi > availableSlots) {
          throw new Error('Not enough open slots to add AI players.');
        }

        for (let i = 0; i < neededAi; i += 1) {
          await apiClient.addAIPlayerToParty(sessionId);
        }
        await loadSessionStatus();
      }

      await apiClient.startPartySession(sessionId);
      // WebSocket will trigger navigation to game page
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start party');
      setIsStarting(false);
    }
  };

  const handleLeave = async () => {
    if (!sessionId) return;

    try {
      await apiClient.leavePartySession(sessionId);
      navigate('/party');
    } catch (err) {
      console.error('Failed to leave party:', err);
      navigate('/party');
    }
  };

  const handleCopyCode = () => {
    if (sessionStatus?.party_code) {
      navigator.clipboard.writeText(sessionStatus.party_code);
      // Could show a toast notification here
    }
  };

  const handleAddAI = async () => {
    if (!sessionId) return;

    setIsAddingAI(true);
    try {
      await apiClient.addAIPlayerToParty(sessionId);
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

    setIsPinging(true);
    try {
      await apiClient.pingParty(sessionId);
      setNotification('Ping sent to everyone in your party.');
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ping players');
      setTimeout(() => setError(null), 4000);
    } finally {
      setIsPinging(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
      </div>
    );
  }

  if (error || !sessionStatus) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-md w-full tile-card p-8 slide-up-enter text-center space-y-4">
          <div className="flex justify-center mb-4">
            <PartyIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-2">Session Not Found</h2>
          <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
            <p className="text-sm text-red-800">{error || 'Session not found'}</p>
          </div>
          <button
            onClick={() => navigate('/party')}
            className="w-full bg-quip-navy hover:bg-quip-teal text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            Back to Party Mode
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <PartyIcon className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Party Lobby</h1>
          </div>
          <p className="text-quip-teal">Players are marked ready whenever they're in this lobby.</p>
        </div>

        <div className="space-y-6">
          {/* Notification Display */}
          {notification && (
            <div className="space-y-3">
              <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4 text-center">
                <p className="text-quip-navy font-semibold">{notification}</p>
              </div>
            </div>
          )}

          {/* Party Code Display */}
          <div className="tile-card shadow-tile p-6 text-center bg-quip-orange bg-opacity-5 border-2 border-quip-orange">
            <h2 className="text-sm font-semibold text-quip-teal uppercase mb-2">Party Code</h2>
            <div
              onClick={handleCopyCode}
              className="text-5xl font-bold font-mono text-quip-orange-deep tracking-widest cursor-pointer hover:text-quip-orange transition-colors"
              title="Click to copy"
            >
              {sessionStatus.party_code}
            </div>
            <p className="text-sm text-quip-teal mt-2">Click to copy code</p>
          </div>

          {/* Session Info */}
          <div className="tile-card shadow-tile-sm p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-quip-teal">Humans Ready</p>
                <p className="text-2xl font-display font-bold text-quip-navy">
                  {humanReadyCount} / {humanParticipants.length}
                </p>
              </div>
              <div>
                <p className="text-sm text-quip-teal">Total Players</p>
                <p className="text-2xl font-display font-bold text-quip-navy">
                  {totalCount} / {maxPlayers}
                </p>
              </div>
              <div>
                <p className="text-sm text-quip-teal">Minimum to Start</p>
                <p className="text-2xl font-display font-bold text-quip-navy">{minPlayers}</p>
              </div>
            </div>
            {!hasEnoughPlayers && (
              <p className="text-xs text-quip-teal mt-2">
                Need {neededAi} more player{neededAi === 1 ? '' : 's'} before starting.
              </p>
            )}
          </div>

          {/* Player List */}
          <div className="tile-card shadow-tile p-4">
            <h3 className="text-lg font-display font-bold text-quip-navy mb-4">Players</h3>
            <div className="space-y-2">
              {participants.map((participant: PartyParticipant) => (
                <div
                  key={participant.participant_id}
                  className="flex items-center justify-between p-3 bg-quip-cream rounded-tile"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        participant.status === 'READY'
                          ? 'bg-quip-turquoise'
                          : 'bg-gray-300'
                      }`}
                      title={participant.status === 'READY' ? 'Ready' : 'Not ready'}
                    />
                    <span className="font-semibold text-quip-navy flex items-center gap-2">
                      {participant.username}
                      {participant.is_ai && <BotIcon className="w-4 h-4" />}
                    </span>
                    {participant.is_host && (
                      <span className="px-2 py-1 text-xs font-semibold text-quip-orange-deep bg-quip-orange bg-opacity-20 rounded-tile">
                        HOST
                      </span>
                    )}
                    {participant.player_id === player?.player_id && (
                      <span className="px-2 py-1 text-xs font-semibold text-quip-turquoise bg-quip-turquoise bg-opacity-20 rounded-tile">
                        YOU
                      </span>
                    )}
                    {participant.is_ai && (
                      <span className="px-2 py-1 text-xs font-semibold text-quip-navy bg-quip-cream border border-quip-navy rounded-tile">
                        AI
                      </span>
                    )}
                  </div>
                  <span className={`text-sm font-semibold ${
                    participant.status === 'READY' ? 'text-quip-turquoise' : 'text-gray-500'
                  }`}>
                    {participant.status === 'READY' ? 'Ready' : 'Waiting...'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            {/* Ping Button (host only) */}
            {isHost && (
              <button
                onClick={handlePingPlayers}
                disabled={isPinging}
                className="w-full border-2 border-quip-navy text-quip-navy bg-white hover:bg-quip-navy hover:text-white font-semibold py-3 px-4 rounded-tile transition-all disabled:opacity-60"
              >
                {isPinging ? 'Pinging players...' : 'Ping Everyone'}
              </button>
            )}

            {/* Add AI Player Button (host only) */}
            {isHost && totalCount < maxPlayers && (
              <button
                onClick={handleAddAI}
                disabled={isAddingAI}
                className="w-full bg-quip-teal hover:bg-quip-turquoise text-white font-semibold py-3 px-4 rounded-tile transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
                    ? 'bg-quip-orange hover:bg-quip-orange-deep text-white hover:shadow-tile-sm'
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
              <p className="text-sm text-center text-quip-teal">
                Waiting for {humanNotReady.length} human player{humanNotReady.length === 1 ? '' : 's'} to return to the lobby.
              </p>
            )}
            {isHost && needsAutoAiStart && (
              <p className="text-sm text-center text-quip-teal">
                All humans are ready! We'll add {neededAi} AI teammate{neededAi === 1 ? '' : 's'} and start immediately.
              </p>
            )}
            {isHost && !hasEnoughPlayers && !needsAutoAiStart && allHumansReady && (
              <p className="text-sm text-center text-quip-teal">
                Need at least {minPlayers} total players to start.
              </p>
            )}

            {/* Leave Button */}
            <button
              onClick={handleLeave}
              className="w-full border-2 border-quip-navy bg-white hover:bg-quip-navy hover:text-white text-quip-navy font-semibold py-3 px-4 rounded-tile transition-all"
            >
              Leave Party
            </button>
          </div>

          {/* Back to Dashboard Button */}
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise py-2 font-medium transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span>Back to Dashboard</span>
          </button>

          {/* Connection Status */}
          <div className="mt-6 p-4 bg-quip-navy bg-opacity-5 rounded-tile">
            <p className="text-sm text-center text-quip-teal">
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
