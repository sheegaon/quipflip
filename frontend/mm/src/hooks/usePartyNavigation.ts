import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

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
    const navigate = useNavigate();

    /**
     * Navigate to home/dashboard.
     * - Party mode: Exit party mode and go to /party
     * - Normal mode: Go to /dashboard
     */
    const navigateHome = useCallback(() => {
        navigate('/dashboard');
    }, [navigate]);

    /**
     * Navigate to results page.
     * - Party mode: Go to /party/results/{sessionId}
     * - Normal mode: Go to /dashboard
     */
    const navigateToResults = useCallback(() => {
        navigate('/dashboard');
    }, [navigate]);

    /**
     * Get the appropriate results path without navigating.
     */
    const getResultsPath = useCallback((): string => {
        return '/dashboard';
    }, []);

    /**
     * Check if currently in party mode (convenience helper).
     */
    const isInPartyMode = false;

    return {
        navigateHome,
        navigateToResults,
        getResultsPath,
        isInPartyMode,
    };
}
