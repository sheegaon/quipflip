/**
 * Session Detection Service
 * Implements the user session detection flow on app load
 */

import { apiClient } from '../api/client';
import { getOrCreateVisitorId, isReturningVisitor } from '../utils/visitorId';
import { SessionState, SessionDetectionResult } from '../types/session';

/**
 * Detect user session state on app load
 *
 * Flow:
 * 1. Try GET /player/balance (with withCredentials for HTTP-only cookies)
 * 2. If 200: Returning, signed-in user
 * 3. If 401: Try POST /auth/refresh, then retry balance
 * 4. If still 401: Check visitor ID
 *    - Has visitor ID: Returning visitor, not signed in
 *    - No visitor ID: New visitor
 *
 * @param signal Optional AbortSignal for cancellation
 * @returns SessionDetectionResult with user state and data
 */
export async function detectUserSession(
  signal?: AbortSignal
): Promise<SessionDetectionResult> {
  // Always ensure visitor ID exists (creates if not present)
  const visitorId = getOrCreateVisitorId();

  try {
    // Step 1: Try to get player balance (validates auth via HTTP-only cookies)
    const balanceResponse = await apiClient.getBalance(signal);

    // Success! User is authenticated
    return {
      state: SessionState.RETURNING_USER,
      isAuthenticated: true,
      username: apiClient.getStoredUsername() || undefined,
      visitorId,
      player: balanceResponse,
    };
  } catch (error: any) {
    // If we get a network error or other non-auth error, still check visitor status
    if (error?.response?.status !== 401) {
      console.warn('Session detection failed with non-auth error:', error);

      // Check if we have a returning visitor
      if (isReturningVisitor()) {
        return {
          state: SessionState.RETURNING_VISITOR,
          isAuthenticated: false,
          visitorId,
        };
      }

      return {
        state: SessionState.NEW,
        isAuthenticated: false,
        visitorId,
      };
    }

    // Step 2: Got 401, check if we have stored credentials that suggest we should try refresh
    const storedUsername = apiClient.getStoredUsername();

    if (storedUsername) {
      try {
        // Step 3: Try to refresh the token
        await apiClient.refreshToken();

        // Step 4: Retry balance check
        const retryBalanceResponse = await apiClient.getBalance(signal);

        // Refresh succeeded!
        return {
          state: SessionState.RETURNING_USER,
          isAuthenticated: true,
          username: storedUsername,
          visitorId,
          player: retryBalanceResponse,
        };
      } catch (refreshError) {
        // Refresh failed, clear stale credentials
        console.info('Token refresh failed, clearing stale session');
        apiClient.clearSession();
      }
    }

    // Step 5: Not authenticated - determine if returning visitor or new
    if (isReturningVisitor()) {
      return {
        state: SessionState.RETURNING_VISITOR,
        isAuthenticated: false,
        visitorId,
      };
    }

    return {
      state: SessionState.NEW,
      isAuthenticated: false,
      visitorId,
    };
  }
}

/**
 * Get a user-friendly message based on session state
 * Useful for welcome messages and UI copy
 */
export function getSessionMessage(sessionState: SessionState, username?: string): string {
  switch (sessionState) {
    case SessionState.RETURNING_USER:
      return username ? `Welcome back, ${username}!` : 'Welcome back!';
    case SessionState.RETURNING_VISITOR:
      return 'Welcome back! Ready to play?';
    case SessionState.NEW:
      return 'Welcome to QuipFlip!';
    case SessionState.CHECKING:
      return 'Loading...';
    default:
      return 'Welcome!';
  }
}

/**
 * Store visitor ID with player account for attribution
 * Call this when a user creates or upgrades an account
 *
 * @param visitorId The visitor ID to associate
 * @param username The username of the newly created account
 */
export function associateVisitorWithPlayer(visitorId: string, username: string): void {
  // Store the association in localStorage for potential backend sync
  const associationKey = `quipflip_visitor_association_${username}`;
  localStorage.setItem(associationKey, JSON.stringify({
    visitorId,
    username,
    associatedAt: new Date().toISOString(),
  }));

  console.info(`Associated visitor ${visitorId} with player ${username}`);
}

/**
 * Get visitor association for a username
 */
export function getVisitorAssociation(username: string): { visitorId: string; associatedAt: string } | null {
  const associationKey = `quipflip_visitor_association_${username}`;
  const data = localStorage.getItem(associationKey);

  if (!data) return null;

  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}
