import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';
import { CircleIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { quipflipBranding } from '@crowdcraft/utils/brandedMessages.ts';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import type { QFPartyContext } from '@crowdcraft/api/types.ts';
import { usePartyRoundStarter } from '../hooks/usePartyRoundStarter';
import { useGame } from '../contexts/GameContext';

const { loadingMessages } = quipflipBranding;

/**
 * Party Game controller - kicks off party mode using the standard round flows.
 */
export const PartyGame: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { state: gameState } = useGame();
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
        if (gameState.activeRound?.round_type && gameState.activeRound.state?.status === 'active') {
          const route = `/${gameState.activeRound.round_type}`;
          const currentStep = gameState.activeRound.round_type;
          startPartyMode(sessionId, currentStep, initialSessionConfigRef.current ?? undefined);
          setCurrentStep(currentStep);
          navigate(route, { replace: true });
          return;
        }

        const status = await apiClient.qfGetPartyState(sessionId);
        const selfParticipant = gameState.player
          ? status.participants.find((participant) => participant.player_id === gameState.player?.player_id)
          : null;
        const referenceParticipant = selfParticipant ?? status.participants[0] ?? null;
        const sessionConfig = referenceParticipant
          ? {
              prompts_per_player: referenceParticipant.prompts_required,
              copies_per_player: referenceParticipant.copies_required,
              votes_per_player: referenceParticipant.votes_required,
            }
          : undefined;

        if (selfParticipant || referenceParticipant) {
          partyActions.updateFromPartyContext({
            session_id: status.session_id,
            current_phase: status.current_phase,
            version: status.version,
            phase_expires_at: status.phase_expires_at ?? null,
            your_progress: {
              prompts_submitted: selfParticipant?.prompts_submitted ?? 0,
              prompts_required: referenceParticipant?.prompts_required ?? 0,
              copies_submitted: selfParticipant?.copies_submitted ?? 0,
              copies_required: referenceParticipant?.copies_required ?? 0,
              votes_submitted: selfParticipant?.votes_submitted ?? 0,
              votes_required: referenceParticipant?.votes_required ?? 0,
            },
            session_progress: {
              players_ready_for_next_phase: status.progress.players_ready_for_next_phase,
              total_players: status.progress.total_players,
            },
          } satisfies QFPartyContext);
        }

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
        startPartyMode(sessionId, step, sessionConfig ?? initialSessionConfigRef.current ?? undefined);
        setCurrentStep(step);

        if (step === 'prompt') {
          await startRoundForPhase('prompt', {
            sessionId,
            sessionConfigOverride: sessionConfig ?? initialSessionConfigRef.current,
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
    gameState.activeRound,
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
            <CircleIcon className="w-16 h-16" />
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
