import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyMode } from '../contexts/PartyModeContext';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { loadingMessages } from '../utils/brandedMessages';
import apiClient, { extractErrorMessage } from '../api/client';
import type { StartPartyPromptResponse } from '../api/types';

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { actions: gameActions } = useGame();
  const { state: partyState, actions: partyActions } = usePartyMode();
  // Remove usage of normal round starters
  // const { startPromptRound, startCopyRound, startVoteRound } = gameActions;
  const { startPartyMode, setCurrentStep } = partyActions;
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
        const roundData = await apiClient.startPartyPromptRound(sessionId) as StartPartyPromptResponse;

        const partyContext = roundData.party_context;

        // Initialize party mode with configuration from the response
        if (partyContext) {
          startPartyMode(sessionId, 'prompt', {
            prompts_per_player: partyContext.your_progress.prompts_required,
            copies_per_player: partyContext.your_progress.copies_required,
            votes_per_player: partyContext.your_progress.votes_required,
            min_players: 0,
            max_players: 0,
          });
          setCurrentStep('prompt');
          partyActions.updateFromPartyContext(partyContext);
        } else {
          startPartyMode(sessionId, 'prompt', partyState.sessionConfig ?? undefined);
          setCurrentStep('prompt');
        }

        gameActions.updateActiveRound({
          round_type: 'prompt',
          round_id: roundData.round_id,
          expires_at: roundData.expires_at,
          state: {
            round_id: roundData.round_id,
            prompt_text: roundData.prompt_text,
            expires_at: roundData.expires_at,
            cost: roundData.cost,
            status: 'active',
          }
        });
        navigate('/prompt', { replace: true });
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
    gameActions,
    partyActions,
    partyState.sessionConfig,
  ]);

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
