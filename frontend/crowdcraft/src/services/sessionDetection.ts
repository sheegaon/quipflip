/**
 * Session Detection Service
 * Implements the user session detection flow on app load
 */

import { apiClient } from '../api/client.ts';
import { getOrCreateVisitorId, getVisitorId } from '../utils';
import { SessionState, SessionDetectionResult } from '../types/session.ts';
import { createLogger } from '../utils/logger.ts';
import type { AuthSessionResponse, GameType, Player } from '../api/types.ts';

interface ErrorWithStatus {
  name?: string;
  code?: string;
  status?: number;
  response?: {
    status?: number;
  };
}

const getStatusCode = (error: unknown): number | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  const maybeError = error as ErrorWithStatus;
  return maybeError.response?.status ?? maybeError.status;
};

const isCanceledRequest = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as ErrorWithStatus;
  return maybeError.name === 'CanceledError' || maybeError.code === 'ERR_CANCELED';
};

const logger = createLogger('SessionDetection');

/**
 * Detect user session state on app load
 *
 * Flow:
 * 1. Try GET /auth/session (with withCredentials for HTTP-only cookies) for the requested game
 * 2. If 200: Returning, signed-in user with optional per-game snapshot
 * 3. If 401: Try POST /auth/refresh, then retry /auth/session
 * 4. If still 401: Check visitor ID
 *    - Has visitor ID: Returning visitor, not signed in
 *    - No visitor ID: New visitor
 *
 * @param signal Optional AbortSignal for cancellation
 * @returns SessionDetectionResult with user state and data
 */
export async function detectUserSession(
  gameType: GameType,
  signal?: AbortSignal
): Promise<SessionDetectionResult> {
  // Check if visitor ID exists BEFORE creating one to distinguish new vs returning visitors
  const existingVisitorId = getVisitorId();
  const isReturningVisitor = existingVisitorId !== null;

  // Now ensure visitor ID exists (creates if not present)
  const visitorId = getOrCreateVisitorId();

  try {
    // Step 1: Try to resolve global session (validates auth via HTTP-only cookies)
    const sessionResponse = await apiClient.getAuthSession(gameType, signal);

    // Success! User is authenticated
    if (sessionResponse.username) {
      apiClient.setSession(sessionResponse.username);
    }

    return buildSessionResult(sessionResponse, visitorId);
  } catch (error: unknown) {
    // Handle request cancellation silently
    if (isCanceledRequest(error)) {
      logger.debug('Session detection request canceled');
      throw error; // Re-throw to let caller handle
    }

    // Check for 401 status - can be in error.response.status or error.status (after axios normalization)
    const statusCode = getStatusCode(error);

    // If we get a network error or other non-auth error, still check visitor status
    if (statusCode !== 401) {
      logger.warn('Session detection failed with non-auth error:', error);

      // Check if this is a returning visitor based on pre-existing visitor ID
      if (isReturningVisitor) {
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

    // Got expected 401 - user not authenticated, this is normal
    logger.debug('User not authenticated (401), checking visitor status');

    // Step 2: Got 401, check if we have stored credentials that suggest we should try refresh
    const storedUsername = apiClient.getStoredUsername();

    if (storedUsername) {
      try {
        // Step 3: Try to refresh the token
        await apiClient.refreshToken();

        // Step 4: Retry session lookup
        const refreshedSession = await apiClient.getAuthSession(gameType, signal);

        // Refresh succeeded! Use username from response if available, fallback to stored
        const username = refreshedSession.username || storedUsername;
        if (username) {
          apiClient.setSession(username);
        }

        return buildSessionResult(refreshedSession, visitorId);
      } catch (refreshError) {
        // Refresh failed, clear stale credentials
        logger.info('Token refresh failed, clearing stale session', refreshError);
        apiClient.clearSession();
      }
    }

    // Step 5: Not authenticated - determine if returning visitor or new
    if (isReturningVisitor) {
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

function buildSessionResult(
  session: AuthSessionResponse,
  visitorId: string
): SessionDetectionResult {
  const normalizedPlayer = normalizeGamePlayer(session);

  return {
    state: SessionState.RETURNING_USER,
    isAuthenticated: true,
    username: session.username || apiClient.getStoredUsername() || undefined,
    visitorId,
    player: normalizedPlayer,
  };
}

function normalizeGamePlayer(session: AuthSessionResponse): Player | undefined {
  const wallet = session.game_data?.wallet ?? session.legacy_wallet ?? undefined;
  const vault = session.game_data?.vault ?? session.legacy_vault ?? undefined;

  if (wallet === undefined && vault === undefined) {
    return undefined;
  }

  return {
    player_id: session.player.player_id,
    username: session.player.username,
    email: session.player.email || '',
    wallet: wallet ?? 0,
    vault: vault ?? 0,
    starting_balance: (wallet ?? 0) + (vault ?? 0),
    daily_bonus_available: true,
    daily_bonus_amount: 0,
    last_login_date: session.player.last_login_date || null,
    outstanding_prompts: 0,
    created_at: session.player.created_at,
    is_guest: session.player.is_guest,
    is_admin: session.player.is_admin,
    locked_until: null,
    flag_dismissal_streak: undefined,
  };
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
      return 'Welcome to MemeMint!';
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

  logger.info(`Associated visitor ${visitorId} with player ${username}`);
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
  } catch (error) {
    logger.error(`Failed to parse visitor association for ${username}:`, error);
    return null;
  }
}
