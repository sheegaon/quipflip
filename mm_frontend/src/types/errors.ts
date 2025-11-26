/**
 * Centralized error type definitions for API and application errors.
 *
 * This file provides type-safe error handling throughout the application.
 */

/**
 * Standard API error response from the backend.
 */
export interface ApiError {
  detail: string;
}

/**
 * Known API error codes returned by the backend.
 * These correspond to specific error conditions documented in API.md.
 */
export type ApiErrorCode =
  | 'insufficient_balance'
  | 'already_in_round'
  | 'expired'
  | 'already_voted'
  | 'already_claimed_today'
  | 'duplicate_phrase'
  | 'invalid_word'
  | 'no_prompts_available'
  | 'no_phrasesets_available'
  | 'max_outstanding_quips'
  | 'vote_lockout_active'
  | 'not_a_guest'
  | 'email_taken'
  | 'invalid_credentials'
  | 'player_not_found'
  | 'round_not_found'
  | 'phraseset_not_found'
  | 'not_a_contributor'
  | 'not_finalized'
  | 'missing_identifier'
  | 'flag_already_resolved'
  | 'invalid_action';

/**
 * Extended error information with optional error code.
 */
export interface DetailedApiError extends ApiError {
  code?: ApiErrorCode;
  statusCode?: number;
}

/**
 * Type guard to check if an error is an API error with a detail field.
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'detail' in error &&
    typeof (error as Record<string, unknown>).detail === 'string'
  );
}

/**
 * Type guard to check if an error is a standard Error object.
 */
export function isError(error: unknown): error is Error {
  return error instanceof Error;
}

/**
 * Type guard to check if an error has a message property.
 */
export function hasMessage(error: unknown): error is { message: string } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as Record<string, unknown>).message === 'string'
  );
}

/**
 * Type guard to check if an error is a network error (no response received).
 */
export function isNetworkError(error: unknown): boolean {
  if (!isError(error)) return false;

  // Axios network errors typically have message containing these patterns
  const networkPatterns = [
    'Network Error',
    'timeout',
    'ECONNREFUSED',
    'ENOTFOUND',
    'ETIMEDOUT',
  ];

  return networkPatterns.some(pattern =>
    error.message.toLowerCase().includes(pattern.toLowerCase())
  );
}

/**
 * Extract a user-friendly error message from any error type.
 *
 * @param error - The error to extract a message from
 * @param fallback - Fallback message if no message can be extracted
 * @returns A user-friendly error message
 */
export function getErrorMessage(error: unknown, fallback = 'An unexpected error occurred'): string {
  // Check for API error with detail
  if (isApiError(error)) {
    return error.detail;
  }

  // Check for Error instance
  if (isError(error)) {
    return error.message;
  }

  // Check for object with message property
  if (hasMessage(error)) {
    return error.message;
  }

  // Check for string
  if (typeof error === 'string') {
    return error;
  }

  // Return fallback
  return fallback;
}

/**
 * Map of API error codes to user-friendly messages.
 */
export const ERROR_MESSAGES: Record<ApiErrorCode, string> = {
  insufficient_balance: "You don't have enough MemeCoins for this action.",
  already_in_round: "You're already in an active round. Complete it first.",
  expired: "This round has expired. Please start a new one.",
  already_voted: "You've already voted on this phraseset.",
  already_claimed_today: "You've already claimed your daily bonus today.",
  duplicate_phrase: "This phrase has already been submitted.",
  invalid_word: "One or more words in your phrase are invalid.",
  no_prompts_available: "No prompts are currently available. Please try again later.",
  no_phrasesets_available: "No phrasesets are available for practice.",
  max_outstanding_quips: "You have too many active prompts. Complete some first.",
  vote_lockout_active: "You're temporarily locked from voting. Try again later.",
  not_a_guest: "This action is only available for guest accounts.",
  email_taken: "This email address is already registered.",
  invalid_credentials: "Invalid email or password.",
  player_not_found: "Player not found.",
  round_not_found: "Round not found.",
  phraseset_not_found: "Phraseset not found.",
  not_a_contributor: "You're not a contributor to this phraseset.",
  not_finalized: "This phraseset is not yet finalized.",
  missing_identifier: "Missing required identifier.",
  flag_already_resolved: "This flag has already been resolved.",
  invalid_action: "Invalid action specified.",
};

/**
 * Get a user-friendly error message from an API error code.
 * Falls back to the error detail if no mapping exists.
 */
export function getUserFriendlyError(error: unknown): string {
  if (!isApiError(error)) {
    return getErrorMessage(error);
  }

  // Check if the detail matches a known error code
  const detail = error.detail as ApiErrorCode;
  if (detail in ERROR_MESSAGES) {
    return ERROR_MESSAGES[detail];
  }

  // Check for network errors
  if (isNetworkError(error)) {
    return 'Network connection lost. Please check your internet.';
  }

  // Return the detail as-is if no mapping found
  return error.detail;
}
