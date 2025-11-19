import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyWebSocket } from '../hooks/usePartyWebSocket';
import apiClient from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { loadingMessages } from '../utils/brandedMessages';
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

  // Start round for current phase - wrapped in useCallback to prevent stale closures
  const startRoundForCurrentPhase = useCallback(async (phase: string) => {
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
  }, [sessionId]);

  // Load session status - wrapped in useCallback to prevent stale closures
  const loadSessionStatus = useCallback(async () => {
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
  }, [sessionId, navigate, activeRound, isPhaseComplete, waitingForPhaseTransition, startRoundForCurrentPhase]);

  useEffect(() => {
    loadSessionStatus();
  }, [loadSessionStatus]);

  // WebSocket handlers - wrapped in useCallback to prevent reconnection on every render
  const handlePhaseTransition = useCallback((data: unknown) => {
    console.log('Phase transition:', data);
    setWaitingForPhaseTransition(false);
    setActiveRound(null);
    setPhraseInput('');
    setSelectedPhrase(null);
    loadSessionStatus();
  }, [loadSessionStatus]);

  const handleProgressUpdate = useCallback((data: unknown) => {
    console.log('Progress update:', data);
    loadSessionStatus();
  }, [loadSessionStatus]);

  const handleSessionCompleted = useCallback((data: unknown) => {
    console.log('Session completed:', data);
    navigate(`/party/results/${sessionId}`);
  }, [navigate, sessionId]);

  const { connected: wsConnected } = usePartyWebSocket({
    sessionId: sessionId ?? '',
    onPhaseTransition: handlePhaseTransition,
    onProgressUpdate: handleProgressUpdate,
    onSessionCompleted: handleSessionCompleted,
  });

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
    if (!activeRound || activeRound.round_type !== 'prompt') return null;

    return (
      <div className="space-y-4">
        <h2 className="text-xl font-display font-bold text-quip-navy">Write Your Best Original Phrase</h2>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4">
          <p className="text-sm text-quip-navy">
            <strong>💡 Tip:</strong> Create a phrase that will fool others into thinking it's a real definition!
          </p>
        </div>

        {/* Prompt Display */}
        <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 relative min-h-[100px] flex items-center">
          <p className="text-xl md:text-2xl text-center font-display font-semibold text-quip-navy flex-1">
            {activeRound.prompt_text}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Input Form */}
        <div>
          <input
            type="text"
            value={phraseInput}
            onChange={(e) => setPhraseInput(e.target.value.toUpperCase())}
            placeholder="Enter your phrase..."
            className="w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise uppercase"
            maxLength={100}
          />
          <p className="text-sm text-quip-teal mt-1">
            2-5 words (4-100 characters), A-Z and spaces only
          </p>
        </div>

        <button
          onClick={handleSubmitPrompt}
          disabled={!phraseInput.trim() || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
            phraseInput.trim() && !submitting
              ? 'bg-quip-navy hover:bg-quip-teal text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? loadingMessages.submitting : 'Submit Phrase'}
        </button>
      </div>
    );
  };

  const renderCopyPhase = () => {
    if (!activeRound || activeRound.round_type !== 'copy') return null;

    // Get the original phrase from the discriminated union type
    const originalPhrase = activeRound.original_phrase;

    return (
      <div className="space-y-4">
        <h2 className="text-xl font-display font-bold text-quip-navy">Write a Convincing Copy</h2>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4">
          <p className="text-sm text-quip-navy">
            <strong>💡 Your goal:</strong> Write a phrase that <em>could have been the original</em> and might trick voters.
            <br />
            <strong>Do:</strong> stay close in meaning. <strong>Don't:</strong> repeat the original exactly.
          </p>
        </div>

        {/* Original Phrase */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6 relative">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">The original answer was:</p>
          <p className="text-3xl text-center font-display font-bold text-quip-turquoise">
            {originalPhrase}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Input Form */}
        <div>
          <input
            type="text"
            value={phraseInput}
            onChange={(e) => setPhraseInput(e.target.value.toUpperCase())}
            placeholder="Enter your copy..."
            className="w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise uppercase"
            maxLength={100}
          />
          <p className="text-sm text-quip-teal mt-1">
            2-5 words (4-100 characters), A-Z and spaces only
          </p>
        </div>

        <button
          onClick={handleSubmitCopy}
          disabled={!phraseInput.trim() || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
            phraseInput.trim() && !submitting
              ? 'bg-quip-turquoise hover:bg-quip-teal text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? loadingMessages.submitting : 'Submit Copy'}
        </button>
      </div>
    );
  };

  const renderVotePhase = () => {
    if (!activeRound || activeRound.round_type !== 'vote') return null;

    // Get the phrases from the discriminated union type
    const phrases = activeRound.phrases;
    const promptText = activeRound.prompt_text;

    return (
      <div className="space-y-4">
        <h2 className="text-xl font-display font-bold text-quip-navy">Vote for the Original</h2>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4">
          <p className="text-sm text-quip-navy">
            <strong>💡 Your goal:</strong> Identify which phrase is the real original and which are the impostors!
          </p>
        </div>

        {/* Prompt Display */}
        <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-4">
          <p className="text-sm text-quip-teal mb-1 text-center">Original Prompt:</p>
          <p className="text-xl md:text-2xl text-center font-display font-semibold text-quip-navy">
            {promptText}
          </p>
        </div>

        <p className="text-quip-teal text-center font-semibold">
          Which phrase do you think is the real one?
        </p>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Vote Options */}
        <div className="space-y-3">
          {phrases.map((phrase, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedPhrase(phrase)}
              className={`w-full p-4 rounded-tile border-2 text-left transition-all ${
                selectedPhrase === phrase
                  ? 'border-quip-orange bg-quip-orange bg-opacity-10 shadow-tile-sm'
                  : 'border-quip-teal hover:border-quip-orange hover:shadow-tile-xs'
              }`}
            >
              <span className="text-lg font-bold text-quip-navy uppercase">{phrase}</span>
            </button>
          ))}
        </div>

        <button
          onClick={handleSubmitVote}
          disabled={!selectedPhrase || submitting}
          className={`w-full font-bold py-3 px-4 rounded-tile transition-all text-lg ${
            selectedPhrase && !submitting
              ? 'bg-quip-orange hover:bg-quip-orange-deep text-white hover:shadow-tile-sm'
              : 'bg-gray-400 text-white cursor-not-allowed'
          }`}
        >
          {submitting ? loadingMessages.submitting : 'Submit Vote'}
        </button>
      </div>
    );
  };

  const renderWaitingState = () => {
    return (
      <div className="space-y-4">
        <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-8 text-center">
          <div className="flex justify-center mb-4">
            <PartyIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-2">Waiting for Others...</h2>
          <p className="text-quip-teal mb-4">
            You've completed this phase! Waiting for other players to finish.
          </p>
          {sessionStatus && (
            <div className="inline-flex items-center gap-2 bg-white rounded-tile px-4 py-2 border-2 border-quip-turquoise">
              <span className="text-2xl font-bold text-quip-turquoise">
                {sessionStatus.progress.players_ready_for_next_phase}
              </span>
              <span className="text-quip-teal">/</span>
              <span className="text-xl font-bold text-quip-navy">
                {sessionStatus.progress.total_players}
              </span>
              <span className="text-sm text-quip-teal">players ready</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
      </div>
    );
  }

  if (!sessionStatus) {
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
            <h1 className="text-3xl font-display font-bold text-quip-navy">Party Mode</h1>
          </div>
          <p className="text-quip-teal">
            {currentPhase === 'PROMPT' && 'Write original phrases'}
            {currentPhase === 'COPY' && 'Create convincing imitations'}
            {currentPhase === 'VOTE' && 'Vote for the originals'}
          </p>
        </div>

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

        {/* Back to Dashboard Button */}
        <button
          onClick={() => navigate('/dashboard')}
          disabled={submitting}
          className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
          title={submitting ? "Please wait for submission to complete" : "Back to Dashboard"}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>Back to Dashboard</span>
        </button>

        {/* Connection Status */}
        <div className="mt-6 p-4 bg-quip-navy bg-opacity-5 rounded-tile">
          <p className="text-sm text-center text-quip-teal">
            {wsConnected ? '✅ Connected to live updates' : '⚠️ Not connected - updates may be delayed'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default PartyGame;
