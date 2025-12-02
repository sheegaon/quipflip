/**
 * Session Detection Types
 * Defines the different user session states and detection results
 */

import type { Player } from '@crowdcraft/api/types.ts';

/**
 * Time window for determining first-time users (5 minutes in milliseconds)
 * If account creation and last login are within this window, user is considered first-time
 */
const FIRST_TIME_USER_WINDOW_MS = 5 * 60 * 1000;

/**
 * User session state types
 */
export const SessionState = {
  /** New visitor - no auth, no visitor ID */
  NEW: 'new',
  /** Returning visitor - no auth, but has visitor ID */
  RETURNING_VISITOR: 'returning_visitor',
  /** Returning user - authenticated with valid session */
  RETURNING_USER: 'returning_user',
  /** Checking session state */
  CHECKING: 'checking',
} as const;

export type SessionState = typeof SessionState[keyof typeof SessionState];

/**
 * Session detection result
 */
export interface SessionDetectionResult {
  /** Current session state */
  state: SessionState;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  /** Username if authenticated */
  username?: string;
  /** Visitor ID (for both authenticated and anonymous users) */
  visitorId: string;
  /** Player data if authenticated */
  player?: Player;
}

/**
 * Helper to determine if user is first-time vs returning based on dates
 */
export function isFirstTimeUser(createdAt?: string, lastLoginDate?: string): boolean {
  if (!createdAt || !lastLoginDate) return false;

  const created = new Date(createdAt).getTime();
  const lastLogin = new Date(lastLoginDate).getTime();

  return Math.abs(lastLogin - created) < FIRST_TIME_USER_WINDOW_MS;
}
