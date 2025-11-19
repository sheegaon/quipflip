import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '../api/client';
import { Header } from '../components/Header';
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
  const [isReady, setIsReady] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  // Check if current player is host
  const isHost = sessionStatus?.participants.find(p => p.player_id === player?.player_id)?.is_host ?? false;

  // Count ready players
  const readyCount = sessionStatus?.participants.filter(p => p.status === 'READY').length ?? 0;
  const totalCount = sessionStatus?.participants.length ?? 0;
  const minPlayers = sessionStatus?.min_players ?? 3;
  const canStart = isHost && readyCount >= minPlayers;

  // Load session status
  const loadSessionStatus = async () => {
    if (!sessionId) return;

    try {
      const status = await apiClient.getPartySessionStatus(sessionId);
      setSessionStatus(status);

      // Check if we're already ready
      const currentPlayer = status.participants.find(p => p.player_id === player?.player_id);
      setIsReady(currentPlayer?.status === 'READY');

      // If session already started, navigate to game
      if (status.status === 'ACTIVE') {
        navigate(`/party/game/${sessionId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessionStatus();
  }, [sessionId]);

  // WebSocket handlers
  const {
    connected: wsConnected,
    connecting: wsConnecting,
    error: wsError,
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
  });

  const handleToggleReady = async () => {
    if (!sessionId) return;

    try {
      await apiClient.markPartyReady(sessionId);
      setIsReady(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark ready');
    }
  };

  const handleStartParty = async () => {
    if (!sessionId || !canStart) return;

    setIsStarting(true);
    try {
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

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-quip-cream">
        <Header />
        <div className="flex-grow flex items-center justify-center">
          <span className="text-lg font-semibold text-quip-navy">Loading lobby...</span>
        </div>
      </div>
    );
  }

  if (error || !sessionStatus) {
    return (
      <div className="flex min-h-screen flex-col bg-quip-cream">
        <Header />
        <div className="flex-grow flex items-center justify-center p-4">
          <div className="max-w-md w-full space-y-4">
            <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
              <p className="text-sm text-red-800">{error || 'Session not found'}</p>
            </div>
            <button
              onClick={() => navigate('/party')}
              className="w-full bg-quip-navy hover:bg-quip-teal text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Back to Party Mode
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-quip-cream">
      <Header />

      <div className="flex-grow flex items-center justify-center p-4">
        <div className="max-w-2xl w-full space-y-6">
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

          {/* WebSocket Status */}
          {wsError && (
            <div className="tile-card bg-yellow-100 border-2 border-yellow-400 p-3 text-sm text-yellow-800">
              Connection issue: {wsError}. Updates may be delayed.
            </div>
          )}

          {/* Session Info */}
          <div className="tile-card shadow-tile-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-quip-teal">Players Ready</p>
                <p className="text-2xl font-display font-bold text-quip-navy">
                  {readyCount} / {totalCount}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-quip-teal">Minimum Required</p>
                <p className="text-2xl font-display font-bold text-quip-navy">{minPlayers}</p>
              </div>
            </div>
          </div>

          {/* Player List */}
          <div className="tile-card shadow-tile p-4">
            <h3 className="text-lg font-display font-bold text-quip-navy mb-4">Players</h3>
            <div className="space-y-2">
              {sessionStatus.participants.map((participant: PartyParticipant) => (
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
                    <span className="font-semibold text-quip-navy">
                      {participant.username}
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
            {/* Ready Button (for non-host or host who isn't ready) */}
            {(!isHost || !isReady) && (
              <button
                onClick={handleToggleReady}
                disabled={isReady}
                className={`w-full font-bold py-3 px-4 rounded-tile transition-all ${
                  isReady
                    ? 'bg-quip-turquoise text-white cursor-not-allowed'
                    : 'bg-quip-turquoise hover:bg-quip-teal text-white hover:shadow-tile-sm'
                }`}
              >
                {isReady ? '✓ Ready!' : 'Mark Ready'}
              </button>
            )}

            {/* Start Button (host only) */}
            {isHost && (
              <button
                onClick={handleStartParty}
                disabled={!canStart || isStarting}
                className={`w-full font-bold py-3 px-4 rounded-tile transition-all ${
                  canStart && !isStarting
                    ? 'bg-quip-orange hover:bg-quip-orange-deep text-white hover:shadow-tile-sm'
                    : 'bg-gray-400 text-white cursor-not-allowed'
                }`}
              >
                {isStarting ? 'Starting...' : 'Start Party'}
              </button>
            )}

            {!canStart && isHost && (
              <p className="text-sm text-center text-quip-teal">
                Need at least {minPlayers} players ready to start
              </p>
            )}

            {/* Leave Button */}
            <button
              onClick={handleLeave}
              className="w-full bg-gray-200 hover:bg-gray-300 text-quip-navy font-semibold py-3 px-4 rounded-tile transition-colors"
            >
              Leave Party
            </button>
          </div>

          {/* Connection Status Indicator */}
          <div className="text-center text-sm text-quip-teal">
            {wsConnecting && '🔄 Connecting to live updates...'}
            {wsConnected && '✅ Connected'}
            {!wsConnecting && !wsConnected && '⚠️ Not connected'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyLobby;
