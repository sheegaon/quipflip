import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PartyIcon } from '../components/icons/NavigationIcons';
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
  const [isReady, setIsReady] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [isAddingAI, setIsAddingAI] = useState(false);

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
      if (data.reason === 'inactive_player_removed' && data.message) {
        setNotification(data.message);
        setTimeout(() => setNotification(null), 5000); // Clear after 5 seconds
      }
      loadSessionStatus();
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
          <p className="text-quip-teal">Waiting for all players to be ready</p>
        </div>

        <div className="space-y-6">
          {/* Notification Display */}
          {notification && (
            <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4 text-center">
              <p className="text-quip-navy font-semibold">{notification}</p>
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
                className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
                  isReady
                    ? 'bg-quip-turquoise text-white cursor-not-allowed'
                    : 'bg-quip-turquoise hover:bg-quip-teal text-white hover:shadow-tile-sm'
                }`}
              >
                {isReady ? '✓ Ready!' : 'Mark Ready'}
              </button>
            )}

            {/* Add AI Player Button (host only) */}
            {isHost && totalCount < (sessionStatus?.max_players ?? 8) && (
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
                disabled={!canStart || isStarting}
                className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
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
