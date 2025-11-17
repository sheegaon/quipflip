/**
 * Extract error message from various error formats
 * @param error - The error object (unknown type for safety)
 * @param defaultMessage - Default message if error parsing fails
 * @returns A string error message
 */
export const getErrorMessage = (error: unknown, defaultMessage: string): string => {
  if (!error) return defaultMessage;

  // Try different error message paths
  if (typeof error === 'string') return error;

  if (typeof error === 'object' && error !== null) {
    // Check for axios response error structure
    if ('response' in error && typeof error.response === 'object' && error.response !== null) {
      const response = error.response as Record<string, unknown>;
      if ('data' in response && typeof response.data === 'object' && response.data !== null) {
        const data = response.data as Record<string, unknown>;
        if ('detail' in data && typeof data.detail === 'string') {
          return data.detail;
        }
      }
    }

    // Check for message property
    if ('message' in error && typeof error.message === 'string') {
      return error.message;
    }

    // Check for detail property
    if ('detail' in error && typeof error.detail === 'string') {
      return error.detail;
    }
  }

  return defaultMessage;
};
