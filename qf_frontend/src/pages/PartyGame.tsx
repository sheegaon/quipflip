import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '../api/client';
import { Header } from '../components/Header';
import type {
  PartySessionStatusResponse,
  StartPartyRoundResponse,
} from '../api/types';

/**
 * Party Game page - Handles all three game phases (PROMPT, COPY, VOTE)
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();

  const [sessionStatus, setSessionStatus] = useState<PartySessionStatusResponse | null>(null);
  const [activeRound, setActiveRound] = useState<StartPartyRoundResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [phraseInput, setPhraseInput] = useState('');
  const [selectedPhrase, setSelectedPhrase] = useState<string | null>(null);
  const [waitingForPhaseTransition, setWaitingForPhaseTransition] = useState(false);

  // Check if current player has completed their required rounds for current phase
  const currentPlayer = sessionStatus?.participants.find(p => p.player_id === player?.player_id);
  const currentPhase = sessionStatus?.current_phase;

  const isPhaseComplete =
    (currentPhase === 'PROMPT' && (currentPlayer?.prompts_submitted ?? 0) >= (currentPlayer?.prompts_required ?? 1)) ||
    (currentPhase === 'COPY' && (currentPlayer?.copies_submitted ?? 0) >= (currentPlayer?.copies_required ?? 2)) ||
    (currentPhase === 'VOTE' && (currentPlayer?.votes_submitted ?? 0) >= (currentPlayer?.votes_required ?? 3));

  // Load session status
  const loadSessionStatus = async () => {
    if (!sessionId) return;

    try {
      const status = await apiClient.getPartySessionStatus(sessionId);
      setSessionStatus(status);

      // Check if session completed
      if (status.current_phase === 'RESULTS' || status.status === 'COMPLETED') {
        navigate(`/party/results/${sessionId}`);
        return;
      }

      // If we don't have an active round and phase isn't complete, start one
      if (!activeRound && !isPhaseComplete && !waitingForPhaseTransition) {
        await startRoundForCurrentPhase(status.current_phase);
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
  const { connected: wsConnected } = usePartyWebSocket({
    sessionId: sessionId ?? '',
    onPhaseTransition: (data) => {
      console.log('Phase transition:', data);
      setWaitingForPhaseTransition(false);
      setActiveRound(null);
      setPhraseInput('');
      setSelectedPhrase(null);
      loadSessionStatus();
    },
    onProgressUpdate: (data) => {
      console.log('Progress update:', data);
      loadSessionStatus();
    },
    onSessionCompleted: (data) => {
      console.log('Session completed:', data);
      navigate(`/party/results/${sessionId}`);
    },
  });

  const startRoundForCurrentPhase = async (phase: string) => {
    if (!sessionId) return;

    try {
      let roundData: StartPartyRoundResponse;

      switch (phase) {
        case 'PROMPT':
          roundData = await apiClient.startPartyPromptRound(sessionId);
          break;
        case 'COPY':
          roundData = await apiClient.startPartyCopyRound(sessionId);
          break;
        case 'VOTE':
          roundData = await apiClient.startPartyVoteRound(sessionId);
          break;
        default:
          throw new Error(`Unknown phase: ${phase}`);
      }

      setActiveRound(roundData);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.message.includes('already submitted')) {
        // Player has completed this phase
        setWaitingForPhaseTransition(true);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to start round');
      }
    }
  };

  const handleSubmitPrompt = async () => {
    if (!sessionId || !activeRound || !phraseInput.trim()) return;

    setSubmitting(true);
    try {
      // Submit the party round
      await apiClient.submitPartyRound(sessionId, activeRound.round_id, phraseInput.trim());

      // Clear state
      setPhraseInput('');
      setActiveRound(null);

      // Reload session status
      await loadSessionStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitCopy = async () => {
    if (!sessionId || !activeRound || !phraseInput.trim()) return;

    setSubmitting(true);
    try {
      await apiClient.submitPartyRound(sessionId, activeRound.round_id, phraseInput.trim());

      setPhraseInput('');
      setActiveRound(null);

      await loadSessionStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitVote = async () => {
    if (!sessionId || !activeRound || !selectedPhrase) return;

    setSubmitting(true);
    try {
      await apiClient.submitPartyRound(sessionId, activeRound.round_id, selectedPhrase);

      setSelectedPhrase(null);
      setActiveRound(null);

      await loadSessionStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  const renderPhaseIndicator = () => {
    if (!sessionStatus) return null;

    const phases = ['LOBBY', 'PROMPT', 'COPY', 'VOTE', 'RESULTS'];
    const currentPhaseIndex = phases.indexOf(sessionStatus.current_phase);

    return (
      <div className="tile-card shadow-tile-sm p-4 mb-4">
        <div className="flex items-center justify-between">
          {phases.slice(1, -1).map((phase, idx) => {
            const phaseIndex = idx + 1;
            const isActive = phaseIndex === currentPhaseIndex;
            const isComplete = phaseIndex < currentPhaseIndex;

            return (
              <React.Fragment key={phase}>
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                      isActive
                        ? 'bg-quip-orange text-white'
                        : isComplete
                        ? 'bg-quip-turquoise text-white'
                        : 'bg-gray-300 text-gray-600'
                    }`}
                  >
                    {isComplete ? '✓' : idx + 1}
                  </div>
                  <span className={`text-xs mt-1 font-semibold ${
                    isActive ? 'text-quip-orange-deep' : 'text-quip-teal'
                  }`}>
                    {phase}
                  </span>
                </div>
                {idx < 2 && (
                  <div className={`flex-1 h-1 mx-2 ${
                    isComplete ? 'bg-quip-turquoise' : 'bg-gray-300'
                  }`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  };

  const renderProgressWidget = () => {
    if (!sessionStatus || !currentPlayer) return null;

    const progress = sessionStatus.progress;
    const playersReady = progress.players_ready_for_next_phase;
    const totalPlayers = progress.total_players;

    return (
      <div className="tile-card shadow-tile-sm p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-quip-teal">Your Progress</span>
          <span className="text-sm font-semibold text-quip-teal">
            {playersReady} / {totalPlayers} players ready
          </span>
        </div>

        <div className="space-y-2 text-sm">
          {currentPhase === 'PROMPT' && (
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Prompts:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer.prompts_submitted} / {currentPlayer.prompts_required}
              </span>
            </div>
          )}
          {currentPhase === 'COPY' && (
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Copies:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer.copies_submitted} / {currentPlayer.copies_required}
              </span>
            </div>
          )}
          {currentPhase === 'VOTE' && (
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Votes:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer.votes_submitted} / {currentPlayer.votes_required}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderPromptPhase = () => {
    if (!activeRound) return null;

    return (
      <div className="tile-card shadow-tile p-6">
        <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Write Your Best Original Phrase</h2>
        <p className="text-quip-teal mb-6">
          Create a phrase that will fool others into thinking it's a real definition!
        </p>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-quip-navy mb-2">
            Your Phrase
          </label>
          <input
            type="text"
            value={phraseInput}
            onChange={(e) => setPhraseInput(e.target.value.toUpperCase())}
            placeholder="Enter your phrase..."
            className="w-full px-4 py-3 border-2 border-quip-navy rounded-tile text-lg uppercase focus:outline-none focus:ring-2 focus:ring-quip-orange"
            maxLength={100}
          />
          <p className="text-sm text-quip-teal mt-1">{phraseInput.length} / 100 characters</p>
        </div>

        {error && (
          <div className="tile-card bg-red-100 border-2 border-red-400 p-3 mb-4 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmitPrompt}
          disabled={!phraseInput.trim() || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all ${
            phraseInput.trim() && !submitting
              ? 'bg-quip-orange hover:bg-quip-orange-deep text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? 'Submitting...' : 'Submit Phrase'}
        </button>
      </div>
    );
  };

  const renderCopyPhase = () => {
    if (!activeRound) return null;

    // TODO: Get the original phrase from activeRound
    const originalPhrase = 'PLACEHOLDER'; // This should come from the round data

    return (
      <div className="tile-card shadow-tile p-6">
        <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Write a Convincing Copy</h2>
        <p className="text-quip-teal mb-6">
          Try to mimic this phrase style to fool the voters!
        </p>

        <div className="tile-card bg-quip-orange bg-opacity-10 border-2 border-quip-orange p-4 mb-6">
          <p className="text-sm font-semibold text-quip-teal mb-2">Original Phrase:</p>
          <p className="text-2xl font-bold text-quip-orange-deep">{originalPhrase}</p>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-quip-navy mb-2">
            Your Copy
          </label>
          <input
            type="text"
            value={phraseInput}
            onChange={(e) => setPhraseInput(e.target.value.toUpperCase())}
            placeholder="Enter your copy..."
            className="w-full px-4 py-3 border-2 border-quip-turquoise rounded-tile text-lg uppercase focus:outline-none focus:ring-2 focus:ring-quip-orange"
            maxLength={100}
          />
          <p className="text-sm text-quip-teal mt-1">{phraseInput.length} / 100 characters</p>
        </div>

        {error && (
          <div className="tile-card bg-red-100 border-2 border-red-400 p-3 mb-4 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmitCopy}
          disabled={!phraseInput.trim() || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all ${
            phraseInput.trim() && !submitting
              ? 'bg-quip-turquoise hover:bg-quip-teal text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? 'Submitting...' : 'Submit Copy'}
        </button>
      </div>
    );
  };

  const renderVotePhase = () => {
    if (!activeRound) return null;

    // TODO: Get phrases from activeRound
    const phrases = ['PHRASE1', 'PHRASE2', 'PHRASE3']; // This should come from round data

    return (
      <div className="tile-card shadow-tile p-6">
        <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Vote for the Original</h2>
        <p className="text-quip-teal mb-6">
          Which phrase do you think is the real one?
        </p>

        <div className="space-y-3 mb-6">
          {phrases.map((phrase, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedPhrase(phrase)}
              className={`w-full p-4 rounded-tile border-2 text-left transition-all ${
                selectedPhrase === phrase
                  ? 'border-quip-orange bg-quip-orange bg-opacity-10'
                  : 'border-gray-300 hover:border-quip-orange hover:border-opacity-50'
              }`}
            >
              <span className="text-lg font-bold text-quip-navy">{phrase}</span>
            </button>
          ))}
        </div>

        {error && (
          <div className="tile-card bg-red-100 border-2 border-red-400 p-3 mb-4 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmitVote}
          disabled={!selectedPhrase || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all ${
            selectedPhrase && !submitting
              ? 'bg-quip-orange hover:bg-quip-orange-deep text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? 'Submitting...' : 'Submit Vote'}
        </button>
      </div>
    );
  };

  const renderWaitingState = () => {
    return (
      <div className="tile-card shadow-tile p-8 text-center">
        <div className="text-6xl mb-4">⏳</div>
        <h2 className="text-2xl font-display font-bold text-quip-navy mb-2">Waiting for Others...</h2>
        <p className="text-quip-teal mb-4">
          You've completed this phase! Waiting for other players to finish.
        </p>
        {sessionStatus && (
          <p className="text-sm text-gray-500">
            {sessionStatus.progress.players_ready_for_next_phase} / {sessionStatus.progress.total_players} players ready
          </p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-quip-cream">
        <Header />
        <div className="flex-grow flex items-center justify-center">
          <span className="text-lg font-semibold text-quip-navy">Loading game...</span>
        </div>
      </div>
    );
  }

  if (!sessionStatus) {
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

      <div className="flex-grow p-4">
        <div className="max-w-2xl mx-auto space-y-4">
          {/* Phase Indicator */}
          {renderPhaseIndicator()}

          {/* Progress Widget */}
          {renderProgressWidget()}

          {/* Phase-specific content */}
          {isPhaseComplete || waitingForPhaseTransition ? (
            renderWaitingState()
          ) : (
            <>
              {currentPhase === 'PROMPT' && renderPromptPhase()}
              {currentPhase === 'COPY' && renderCopyPhase()}
              {currentPhase === 'VOTE' && renderVotePhase()}
            </>
          )}

          {/* Connection Status */}
          <div className="text-center text-sm text-quip-teal">
            {wsConnected ? '✅ Connected' : '⚠️ Not connected'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyGame;
