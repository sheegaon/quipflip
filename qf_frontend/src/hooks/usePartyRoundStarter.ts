import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import type { StartPartyCopyResponse, StartPartyPromptResponse, StartPartyVoteResponse } from '../api/types';
import { useGame } from '../contexts/GameContext';
import type { PartyStep, SessionConfig } from '../contexts/PartyModeContext';
import { usePartyMode } from '../contexts/PartyModeContext';

type PartyPhase = Exclude<PartyStep, 'results'>;

interface StartOptions {
  sessionId?: string;
  sessionConfigOverride?: SessionConfig | null;
  replaceHistory?: boolean;
}

/**
 * Centralizes starting party rounds via REST so WebSockets stay notification-only.
 */
export function usePartyRoundStarter() {
  const navigate = useNavigate();
  const { actions: gameActions } = useGame();
  const { updateActiveRound } = gameActions;
  const { state: partyState, actions: partyActions } = usePartyMode();

  const startRoundForPhase = useCallback(
    async (phase: PartyPhase, options?: StartOptions) => {
      const sessionId = options?.sessionId ?? partyState.sessionId;

      if (!sessionId) {
        throw new Error('Cannot start a party round without a session id');
      }

      const replaceHistory = options?.replaceHistory ?? true;
      const configToPersist = options?.sessionConfigOverride ?? partyState.sessionConfig ?? undefined;

      if (!partyState.isPartyMode) {
        partyActions.startPartyMode(sessionId, phase, configToPersist);
      } else {
        partyActions.setCurrentStep(phase);
      }

      if (phase === 'prompt') {
        const roundData = await apiClient.startPartyPromptRound(sessionId) as StartPartyPromptResponse;

        if (roundData.party_context) {
          partyActions.updateFromPartyContext(roundData.party_context);
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

        navigate('/prompt', { replace: replaceHistory });
        return;
      }

      if (phase === 'copy') {
        const roundData = await apiClient.startPartyCopyRound(sessionId) as StartPartyCopyResponse;

        if (roundData.party_context) {
          partyActions.updateFromPartyContext(roundData.party_context);
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

        navigate('/copy', { replace: replaceHistory });
        return;
      }

      const roundData = await apiClient.startPartyVoteRound(sessionId) as StartPartyVoteResponse;

      if (roundData.party_context) {
        partyActions.updateFromPartyContext(roundData.party_context);
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

      navigate('/vote', { replace: replaceHistory });
    },
    [navigate, partyActions, partyState.isPartyMode, partyState.sessionConfig, partyState.sessionId, updateActiveRound]
  );

  const endSessionAndShowResults = useCallback(
    (sessionId?: string) => {
      const targetSessionId = sessionId ?? partyState.sessionId;

      partyActions.endPartyMode();

      if (targetSessionId) {
        navigate(`/party/results/${targetSessionId}`, { replace: true });
      } else {
        navigate('/party/results', { replace: true });
      }
    },
    [navigate, partyActions, partyState.sessionId]
  );

  return { startRoundForPhase, endSessionAndShowResults };
}
