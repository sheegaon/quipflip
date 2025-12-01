import type { ErrorInfo } from 'react';

export interface ErrorReportContext {
  gameState?: Record<string, unknown> | null;
  roundState?: Record<string, unknown> | null;
  userActions?: string[];
  [key: string]: unknown;
}

export interface ErrorReport {
  errorId: string;
  timestamp: string;
  userAgent: string;
  url: string;
  userId?: string;
  error: {
    message: string;
    stack?: string;
    componentStack?: string;
  };
  context: ErrorReportContext;
}

/**
 * Generate a unique error ID for support and tracking
 */
export const generateErrorId = (): string => {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2, 9);
  return `ERR-${timestamp}-${randomPart}`.toUpperCase();
};

/**
 * Sanitize error data to remove sensitive information
 */
export const sanitizeErrorData = (error: Error, errorInfo?: ErrorInfo): ErrorReport['error'] => {
  const errorData: ErrorReport['error'] = {
    message: error.message,
  };

  // Include stack trace in development
  if (import.meta.env.DEV && error.stack) {
    errorData.stack = error.stack;
  }

  // Include component stack if available
  if (errorInfo?.componentStack) {
    errorData.componentStack = errorInfo.componentStack;
  }

  return errorData;
};

/**
 * Log error to console in development mode
 */
export const logErrorToConsole = (
  error: Error,
  errorInfo?: ErrorInfo,
  errorId?: string
): void => {
  if (import.meta.env.DEV) {
    console.group(`🔴 Error ${errorId ? `[${errorId}]` : ''}`);
    console.error('Error:', error);
    if (errorInfo) {
      console.error('Component Stack:', errorInfo.componentStack);
    }
    console.groupEnd();
  }
};

/**
 * Log error to external service in production
 * This is a placeholder for integration with services like Sentry, LogRocket, etc.
 */
export const logErrorToService = (
  error: Error,
  errorInfo?: ErrorInfo,
  context?: ErrorReportContext
): string => {
  const errorId = generateErrorId();

  const errorReport: ErrorReport = {
    errorId,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href,
    error: sanitizeErrorData(error, errorInfo),
    context: context || {},
  };

  // Log to console in development
  logErrorToConsole(error, errorInfo, errorId);

  // In production, send to error tracking service
  if (import.meta.env.PROD) {
    // TODO: Integrate with error tracking service (Sentry, LogRocket, etc.)
    // Example:
    // Sentry.captureException(error, {
    //   contexts: { errorReport },
    // });

    // For now, store in localStorage for debugging
    try {
      const recentErrors = JSON.parse(localStorage.getItem('quipflip_recent_errors') || '[]');
      recentErrors.unshift(errorReport);
      // Keep only the last 10 errors
      localStorage.setItem('quipflip_recent_errors', JSON.stringify(recentErrors.slice(0, 10)));
    } catch (storageError) {
      console.error('Failed to store error report:', storageError);
    }
  }

  return errorId;
};

/**
 * Clear stored error reports
 */
export const clearStoredErrors = (): void => {
  try {
    localStorage.removeItem('quipflip_recent_errors');
  } catch (error) {
    console.error('Failed to clear error reports:', error);
  }
};

/**
 * Get stored error reports for debugging
 */
export const getStoredErrors = (): ErrorReport[] => {
  try {
    return JSON.parse(localStorage.getItem('quipflip_recent_errors') || '[]');
  } catch (error) {
    console.error('Failed to retrieve error reports:', error);
    return [];
  }
};
