import { getContextualErrorMessage } from './errorMessages';

/**
 * Extract error message from various error formats
 * Falls back to a contextual error generator for user-friendly messaging.
 */
export const getErrorMessage = (error: unknown, defaultMessage: string): string => {
  const contextual = getContextualErrorMessage(error);
  if (contextual.message) {
    return contextual.message;
  }

  return defaultMessage;
};
