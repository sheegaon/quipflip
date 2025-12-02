import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';
import apiClient, { extractErrorMessage } from '@/api/client';
import type { StartPartyCopyResponse, StartPartyVoteResponse } from '@crowdcraft/api/types.ts';

type RoundType = 'prompt' | 'copy' | 'vote';

interface TransitionState {
    isTransitioning: boolean;
    error: string | null;
}

/**
 * Coordinates round transitions in party mode.
 *
 * Handles:
 * - Starting the next round via party-specific endpoints
 * - Updating party mode step
 * - Navigation to next round page
 * - Error handling and retry logic
 *
 * Usage:
 *   const { transitionToNextRound, isTransitioning, error } = usePartyRoundCoordinator();
 *
 *   // After successful submission:
 *   useEffect(() => {
 *     if (successMessage && partyState.isPartyMode) {
 *       transitionToNextRound('prompt').catch(err => console.error(err));
 *     }
 *   }, [successMessage]);
 */
export function usePartyRoundCoordinator() {
    const { state: partyState, actions: partyActions } = usePartyMode();
    const navigate = useNavigate();
    const [state, setState] = useState<TransitionState>({
        isTransitioning: false,
        error: null,
    });
    const attemptedRef = useRef(false);

    /**
     * Transition from current round to the next round in party mode.
     *
     * @param currentRound - The round type that just completed
     * @returns Promise that resolves when transition complete
     * @throws Error if transition fails (after all retries)
     */
    const transitionToNextRound = useCallback(
        async (currentRound: RoundType): Promise<void> => {
            // Guard: Only in party mode
            if (!partyState.isPartyMode || !partyState.sessionId) {
                console.warn('transitionToNextRound called but not in party mode');
                return;
            }

            // Guard: Prevent duplicate attempts
            if (attemptedRef.current) {
                console.warn('Transition already in progress, skipping duplicate call');
                return;
            }

            setState({ isTransitioning: true, error: null });
            attemptedRef.current = true;

            // Define transition mappings
            type TransitionConfig =
                | {
                      next: 'copy';
                      endpoint: (sessionId: string) => Promise<StartPartyCopyResponse>;
                      path: string;
                  }
                | {
                      next: 'vote';
                      endpoint: (sessionId: string) => Promise<StartPartyVoteResponse>;
                      path: string;
                  }
                | {
                      next: 'results';
                      endpoint?: undefined;
                      path: string;
                  };

            const transitions: Record<RoundType, TransitionConfig> = {
                prompt: {
                    next: 'copy',
                    endpoint: apiClient.startPartyCopyRound,
                    path: '/copy',
                },
                copy: {
                    next: 'vote',
                    endpoint: apiClient.startPartyVoteRound,
                    path: '/vote',
                },
                vote: {
                    next: 'results',
                    endpoint: undefined, // No endpoint, just navigate
                    path: `/party/results/${partyState.sessionId}`,
                },
            };

            const transition: TransitionConfig = transitions[currentRound];

            try {
                // Special case: vote → results (no round to start, just navigate and end party mode)
                if (transition.next === 'results') {
                    partyActions.endPartyMode();
                    navigate(transition.path, { replace: true });
                    setState({ isTransitioning: false, error: null });
                    return;
                }

                await transition.endpoint(partyState.sessionId);

                // Update party mode step
                partyActions.setCurrentStep(transition.next);

                // Navigate to next round page
                navigate(transition.path, { replace: true });

                setState({ isTransitioning: false, error: null });
                attemptedRef.current = false; // Reset for next transition
            } catch (err) {
                const message =
                    extractErrorMessage(err) || `Unable to start the ${transition.next} round.`;

                setState({ isTransitioning: false, error: message });
                attemptedRef.current = false; // Allow retry

                throw new Error(message);
            }
        },
        [partyState.isPartyMode, partyState.sessionId, navigate, partyActions]
    );

    /**
     * Reset error state (useful for retry buttons)
     */
    const clearError = useCallback(() => {
        setState((prev) => ({ ...prev, error: null }));
        attemptedRef.current = false;
    }, []);

    return {
        transitionToNextRound,
        isTransitioning: state.isTransitioning,
        error: state.error,
        clearError,
    };
}
