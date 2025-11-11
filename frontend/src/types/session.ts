/**
 * Session Detection Types
 * Defines the different user session states and detection results
 */

/**
 * User session state types
 */
export enum SessionState {
  /** New visitor - no auth, no visitor ID */
  NEW = 'new',
  /** Returning visitor - no auth, but has visitor ID */
  RETURNING_VISITOR = 'returning_visitor',
  /** Returning user - authenticated with valid session */
  RETURNING_USER = 'returning_user',
  /** Checking session state */
  CHECKING = 'checking',
}

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
  player?: {
    balance: number;
    created_at?: string;
    last_login_date?: string;
    [key: string]: any;
  };
}

/**
 * Helper to determine if user is first-time vs returning based on dates
 */
export function isFirstTimeUser(createdAt?: string, lastLoginDate?: string): boolean {
  if (!createdAt || !lastLoginDate) return false;

  const created = new Date(createdAt).getTime();
  const lastLogin = new Date(lastLoginDate).getTime();

  // If created and last login are within 5 minutes, consider it first time
  const fiveMinutes = 5 * 60 * 1000;
  return Math.abs(lastLogin - created) < fiveMinutes;
}
