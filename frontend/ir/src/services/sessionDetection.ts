/**
 * Session Detection Service for Initial Reaction
 * Implements the user session detection flow on app load
 */

import { playerAPI } from '../api/client';
import { createLogger } from '@crowdcraft/utils/logger.ts';

const logger = createLogger('SessionDetection');

export const SessionState = {
  CHECKING: 'checking',
  NEW: 'new',
  RETURNING_VISITOR: 'returning_visitor',
  RETURNING_USER: 'returning_user',
} as const;

export type SessionState = typeof SessionState[keyof typeof SessionState];

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

// Visitor ID management
const VISITOR_ID_KEY = 'ir_visitor_id';

export function getVisitorId(): string | null {
  return localStorage.getItem(VISITOR_ID_KEY);
}

export function getOrCreateVisitorId(): string {
  const existing = getVisitorId();
  if (existing) return existing;

  const newId = `v_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  localStorage.setItem(VISITOR_ID_KEY, newId);
  logger.info('Created new visitor ID:', newId);
  return newId;
}

// Username storage
const USERNAME_STORAGE_KEY = 'ir_username';

export function getStoredUsername(): string | null {
  return localStorage.getItem(USERNAME_STORAGE_KEY);
}

export function setStoredUsername(username: string): void {
  localStorage.setItem(USERNAME_STORAGE_KEY, username);
}

export function clearStoredUsername(): void {
  localStorage.removeItem(USERNAME_STORAGE_KEY);
}

export interface SessionDetectionResult {
  state: SessionState;
  isAuthenticated: boolean;
  username?: string;
  visitorId: string;
  player?: {
    wallet: number;
    vault: number;
    daily_bonus_available: boolean;
  };
}

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
 */
export async function detectUserSession(
  _signal?: AbortSignal
): Promise<SessionDetectionResult> {
  // Check if visitor ID exists BEFORE creating one to distinguish new vs returning visitors
  const existingVisitorId = getVisitorId();
  const isReturningVisitor = existingVisitorId !== null;

  // Now ensure visitor ID exists (creates if not present)
  const visitorId = getOrCreateVisitorId();

  // Skip auth check if no stored session - user is not authenticated
  const storedUsername = getStoredUsername();
  if (!storedUsername && !isReturningVisitor) {
    // New visitor with no stored session - skip API call to avoid 401 errors
    return {
      state: SessionState.NEW,
      isAuthenticated: false,
      visitorId,
    };
  }

  try {
    // Step 1: Try to get player balance (validates auth via HTTP-only cookies)
    const balanceResponse = await playerAPI.getBalance();

    // Success! User is authenticated
    // Note: IR API doesn't return username in balance response, use stored username
    const username = storedUsername;

    return {
      state: SessionState.RETURNING_USER,
      isAuthenticated: true,
      username: username ?? undefined,
      visitorId,
      player: balanceResponse,
    };
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

    // Step 2: Not authenticated - determine if returning visitor or new
    if (isReturningVisitor) {
      // Clear stale credentials on 401
      clearStoredUsername();

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
      return 'Welcome to Initial Reaction!';
    case SessionState.CHECKING:
      return 'Loading...';
    default:
      return 'Welcome!';
  }
}

/**
 * Store visitor ID with player account for attribution
 * Call this when a user creates or upgrades an account
 */
export function associateVisitorWithPlayer(visitorId: string, username: string): void {
  const associationKey = `ir_visitor_association_${username}`;
  localStorage.setItem(associationKey, JSON.stringify({
    visitorId,
    username,
    associatedAt: new Date().toISOString(),
  }));

  logger.info(`Associated visitor ${visitorId} with player ${username}`);
}
