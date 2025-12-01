import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';

/**
 * Provides party-aware navigation helpers.
 *
 * Handles conditional navigation based on whether user is in party mode.
 *
 * Usage:
 *   const { navigateHome, navigateToResults } = usePartyNavigation();
 *
 *   <button onClick={navigateHome}>Back</button>
 */
export function usePartyNavigation() {
    const { state: partyState, actions: partyActions } = usePartyMode();
    const navigate = useNavigate();

    /**
     * Navigate to home/dashboard.
     * - Party mode: Exit party mode and go to /party
     * - Normal mode: Go to /dashboard
     */
    const navigateHome = useCallback(() => {
        if (partyState.isPartyMode) {
            partyActions.endPartyMode();
            navigate('/party');
        } else {
            navigate('/dashboard');
        }
    }, [partyState.isPartyMode, partyActions, navigate]);

    /**
     * Navigate to results page.
     * - Party mode: Go to /party/results/{sessionId}
     * - Normal mode: Go to /dashboard
     */
    const navigateToResults = useCallback(() => {
        if (partyState.isPartyMode && partyState.sessionId) {
            partyActions.endPartyMode();
            navigate(`/party/results/${partyState.sessionId}`);
        } else {
            navigate('/dashboard');
        }
    }, [partyState.isPartyMode, partyState.sessionId, partyActions, navigate]);

    /**
     * Get the appropriate results path without navigating.
     */
    const getResultsPath = useCallback((): string => {
        if (partyState.isPartyMode && partyState.sessionId) {
            return `/party/results/${partyState.sessionId}`;
        }
        return '/dashboard';
    }, [partyState.isPartyMode, partyState.sessionId]);

    /**
     * Check if currently in party mode (convenience helper).
     */
    const isInPartyMode = partyState.isPartyMode;

    return {
        navigateHome,
        navigateToResults,
        getResultsPath,
        isInPartyMode,
    };
}
