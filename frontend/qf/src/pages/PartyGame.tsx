import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { loadingMessages } from '../utils/brandedMessages';
import apiClient, { extractErrorMessage } from '../api/client';
import { usePartyRoundStarter } from '../hooks/usePartyRoundStarter';

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { state: partyState, actions: partyActions } = usePartyMode();
  // Remove usage of normal round starters
  // const { startPromptRound, startCopyRound, startVoteRound } = gameActions;
  const { startPartyMode, setCurrentStep } = partyActions;
  const { startRoundForPhase, endSessionAndShowResults } = usePartyRoundStarter();
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialSessionConfigRef = useRef(partyState.sessionConfig);

  useEffect(() => {
    if (!sessionId) {
      setError('Session not found');
      return;
    }

    const beginPartyFlow = async () => {
      setIsStarting(true);
      setError(null);

      try {
        const status = await apiClient.getPartySessionStatus(sessionId);
        const phase = status.current_phase.toLowerCase();

        if (phase === 'results' || status.status === 'COMPLETED') {
          endSessionAndShowResults(sessionId);
          return;
        }

        const phaseToStepMap: Record<string, 'prompt' | 'copy' | 'vote'> = {
          prompt: 'prompt',
          copy: 'copy',
          vote: 'vote',
        };

        const step = phaseToStepMap[phase] ?? 'prompt';
        startPartyMode(sessionId, step, initialSessionConfigRef.current ?? undefined);
        setCurrentStep(step);

        if (step === 'prompt') {
          await startRoundForPhase('prompt', {
            sessionId,
            sessionConfigOverride: initialSessionConfigRef.current,
          });
        } else if (step === 'copy') {
          await startRoundForPhase('copy', { sessionId });
        } else if (step === 'vote') {
          await startRoundForPhase('vote', { sessionId });
        }
      } catch (err) {
        const message = extractErrorMessage(err) || 'Failed to start party round.';
        setError(message);
      } finally {
        setIsStarting(false);
      }
    };

    void beginPartyFlow();
  }, [
    navigate,
    sessionId,
    startPartyMode,
    setCurrentStep,
    startRoundForPhase,
    endSessionAndShowResults,
  ]);

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-turquoise flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-md w-full tile-card p-8 slide-up-enter text-center space-y-4">
          <div className="flex justify-center mb-4">
            <PartyIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-2">Session Not Found</h2>
          <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
            <p className="text-sm text-red-800">{error}</p>
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
    <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center">
      <LoadingSpinner
        isLoading={true}
        message={isStarting ? 'Starting your first quip round...' : loadingMessages.starting}
      />
    </div>
  );
};

export default PartyGame;
