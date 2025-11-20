import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyMode } from '../contexts/PartyModeContext';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { loadingMessages } from '../utils/brandedMessages';
import apiClient, { extractErrorMessage } from '../api/client';

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { actions: gameActions, state: gameState } = useGame();
  const { actions: partyActions, state: partyState } = usePartyMode();
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          partyActions.endPartyMode();
          navigate(`/party/results/${sessionId}`);
          return;
        }

        const phaseToStepMap: Record<string, 'prompt' | 'copy' | 'vote'> = {
          prompt: 'prompt',
          copy: 'copy',
          vote: 'vote',
        };

        const step = phaseToStepMap[phase] ?? 'prompt';
        partyActions.startPartyMode(sessionId, step);
        partyActions.setCurrentStep(step);

        if (step === 'copy') {
          if (gameState.activeRound?.round_type !== 'copy') {
            await gameActions.startCopyRound();
          }
          navigate('/copy', { replace: true });
          return;
        }

        if (step === 'vote') {
          if (gameState.activeRound?.round_type !== 'vote') {
            await gameActions.startVoteRound();
          }
          navigate('/vote', { replace: true });
          return;
        }

        // Default to prompt round
        if (gameState.activeRound?.round_type !== 'prompt') {
          await gameActions.startPromptRound();
        }

        navigate('/prompt', { replace: true });
      } catch (err) {
        const message = extractErrorMessage(err) || 'Failed to start party round.';
        setError(message);
      } finally {
        setIsStarting(false);
      }
    };

    void beginPartyFlow();
  }, [gameActions, gameState.activeRound?.round_type, navigate, partyActions, partyState.currentStep, sessionId]);

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-md w-full tile-card p-8 slide-up-enter text-center space-y-4">
          <div className="flex justify-center mb-4">
            <PartyIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-2">Session Not Found</h2>
          <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
            <p className="text-sm text-red-800">{error}</p>
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
    <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
      <LoadingSpinner
        isLoading={true}
        message={isStarting ? 'Starting your first quip round...' : loadingMessages.starting}
      />
    </div>
  );
};

export default PartyGame;
