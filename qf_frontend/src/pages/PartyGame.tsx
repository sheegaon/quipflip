import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyMode } from '../contexts/PartyModeContext';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { loadingMessages } from '../utils/brandedMessages';
import apiClient, { extractErrorMessage } from '../api/client';
import type { StartPartyPromptResponse, StartPartyCopyResponse, StartPartyVoteResponse } from '../api/types';

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { actions: gameActions } = useGame();
  const { actions: partyActions } = usePartyMode();
  // Remove usage of normal round starters
  // const { startPromptRound, startCopyRound, startVoteRound } = gameActions;
  const { startPartyMode, setCurrentStep, endPartyMode } = partyActions;
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

        // Check if already completed
        if (phase === 'results' || status.status === 'COMPLETED') {
          endPartyMode();
          navigate(`/party/results/${sessionId}`);
          return;
        }

        // Map server phase to client step
        const phaseToStepMap: Record<string, 'prompt' | 'copy' | 'vote'> = {
          prompt: 'prompt',
          copy: 'copy',
          vote: 'vote',
        };

        const step = phaseToStepMap[phase] ?? 'prompt';

        const participantConfig = status.participants[0];
        const sessionConfig = participantConfig
          ? {
              min_players: status.min_players,
              max_players: status.max_players,
              prompts_per_player: participantConfig.prompts_required,
              copies_per_player: participantConfig.copies_required,
              votes_per_player: participantConfig.votes_required,
            }
          : undefined;

        // Initialize party mode (will store session config from first round)
        startPartyMode(sessionId, step, sessionConfig);
        setCurrentStep(step);

        // Start the appropriate round using PARTY-SPECIFIC endpoints
        if (step === 'prompt') {
          const roundData = await apiClient.startPartyPromptRound(sessionId) as StartPartyPromptResponse;

          // Update party context from response
          if (roundData.party_context) {
            partyActions.updateFromPartyContext(roundData.party_context);
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
        } else if (step === 'copy') {
          const roundData = await apiClient.startPartyCopyRound(sessionId) as StartPartyCopyResponse;

          // Update party context from response
          if (roundData.party_context) {
            partyActions.updateFromPartyContext(roundData.party_context);
          }

          gameActions.updateActiveRound({
            round_type: 'copy',
            round_id: roundData.round_id,
            expires_at: roundData.expires_at,
            state: {
              round_id: roundData.round_id,
              original_phrase: roundData.original_phrase,
              prompt_round_id: roundData.prompt_round_id,
              expires_at: roundData.expires_at,
              cost: roundData.cost,
              status: 'active',
              discount_active: false,
            }
          });
          navigate('/copy', { replace: true });
        } else if (step === 'vote') {
          const roundData = await apiClient.startPartyVoteRound(sessionId) as StartPartyVoteResponse;

          // Update party context from response
          if (roundData.party_context) {
            partyActions.updateFromPartyContext(roundData.party_context);
          }

          gameActions.updateActiveRound({
            round_type: 'vote',
            round_id: roundData.round_id,
            expires_at: roundData.expires_at,
            state: {
              round_id: roundData.round_id,
              phraseset_id: roundData.phraseset_id,
              prompt_text: roundData.prompt_text,
              phrases: roundData.phrases,
              expires_at: roundData.expires_at,
              status: 'active',
            }
          });
          navigate('/vote', { replace: true });
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
    endPartyMode,
    gameActions
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
