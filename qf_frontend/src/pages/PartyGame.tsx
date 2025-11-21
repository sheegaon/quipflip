import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyMode } from '../contexts/PartyModeContext';
import { PartyIcon } from '../components/icons/NavigationIcons';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { loadingMessages } from '../utils/brandedMessages';
import apiClient, { extractErrorMessage } from '../api/client';
import type { StartPartyImpostorResponse, StartPartyQuipResponse, StartPartyVoteResponse } from '../api/types';

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { actions: gameActions } = useGame();
  const { state: partyState, actions: partyActions } = usePartyMode();
  // Remove usage of normal round starters
  // const { startQuipRound, startImpostorRound, startVoteRound } = gameActions;
  const { startPartyMode, setCurrentStep, endPartyMode, updateFromPartyContext } = partyActions;
  const { updateActiveRound } = gameActions;
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
          endPartyMode();
          navigate(`/party/results/${sessionId}`);
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
          const roundData = await apiClient.startPartyQuipRound(sessionId) as StartPartyQuipResponse;
          const partyContext = roundData.party_context;

          if (partyContext) {
            updateFromPartyContext(partyContext);
          }

          updateActiveRound({
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
          const roundData = await apiClient.startPartyImpostorRound(sessionId) as StartPartyImpostorResponse;
          const partyContext = roundData.party_context;

          if (partyContext) {
            updateFromPartyContext(partyContext);
          }

          updateActiveRound({
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
              discount_active: roundData.discount_active,
            }
          });
          navigate('/copy', { replace: true });
        } else if (step === 'vote') {
          const roundData = await apiClient.startPartyVoteRound(sessionId) as StartPartyVoteResponse;
          const partyContext = roundData.party_context;

          if (partyContext) {
            updateFromPartyContext(partyContext);
          }

          updateActiveRound({
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
    updateFromPartyContext,
    updateActiveRound,
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
