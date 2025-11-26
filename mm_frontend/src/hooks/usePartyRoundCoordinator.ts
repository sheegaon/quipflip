import { useCallback, useRef, useState } from 'react';

interface TransitionState {
    isTransitioning: boolean;
    error: string | null;
}

/**
 * Previously coordinated round transitions in party mode.
 * Party mode is being removed, so the hook now provides a no-op implementation
 * that preserves the API surface for callers while avoiding unused network
 * calls.
 */
export function usePartyRoundCoordinator() {
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
        async (): Promise<void> => {
            // Guard: Prevent duplicate attempts
            if (attemptedRef.current) {
                console.warn('Transition already in progress, skipping duplicate call');
                return;
            }

            setState({ isTransitioning: true, error: null });
            attemptedRef.current = true;

            try {
                setState({ isTransitioning: false, error: null });
                attemptedRef.current = false; // Reset for next transition
            } catch {
                const message = 'Unable to transition to the next round.';

                setState({ isTransitioning: false, error: message });
                attemptedRef.current = false; // Allow retry

                throw new Error(message);
            }
        },
        []
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
