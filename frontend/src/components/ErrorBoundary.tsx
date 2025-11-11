import React, { Component, ErrorInfo, ReactNode } from 'react';
import { ErrorFallback, type ErrorFallbackProps } from './ErrorFallback';
import { logErrorToService } from '../utils/errorReporting';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string;
  retryCount: number;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: React.ComponentType<ErrorFallbackProps>;
  onError?: (error: Error, errorInfo: ErrorInfo, errorId: string) => void;
  maxRetries?: number;
  resetKeys?: Array<string | number>;
  isAppLevel?: boolean;
}

/**
 * ErrorBoundary Component
 *
 * Catches JavaScript errors anywhere in the component tree and displays fallback UI
 * instead of crashing the entire application.
 *
 * Features:
 * - Catches rendering errors, lifecycle method errors, and constructor errors
 * - Displays user-friendly error message with retry functionality
 * - Logs errors to console (dev) and external service (production)
 * - Generates unique error ID for support tickets
 * - Automatic retry mechanism with configurable limits
 * - Preserves user data when possible
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary fallback={CustomErrorFallback} onError={handleError}>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private readonly maxRetries: number;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: '',
      retryCount: 0,
    };
    this.maxRetries = props.maxRetries || 3;
  }

  /**
   * Update state when an error is caught
   * This is called during the render phase, so side effects are not allowed
   */
  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Log error details after an error has been caught
   * This is called during the commit phase, so side effects are allowed
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to service and get error ID
    const errorId = logErrorToService(error, errorInfo, this.getErrorContext());

    // Update state with error details
    this.setState({
      errorInfo,
      errorId,
    });

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo, errorId);
    }
  }

  /**
   * Reset error boundary when resetKeys change
   */
  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    const { resetKeys } = this.props;
    const { hasError } = this.state;

    // Reset error boundary if resetKeys changed
    if (
      hasError &&
      resetKeys &&
      prevProps.resetKeys &&
      !this.arraysEqual(resetKeys, prevProps.resetKeys)
    ) {
      this.resetErrorBoundary();
    }
  }

  /**
   * Helper to compare reset key arrays
   */
  private arraysEqual(a: Array<string | number>, b: Array<string | number>): boolean {
    if (a.length !== b.length) return false;
    return a.every((val, index) => val === b[index]);
  }

  /**
   * Get error context for logging
   */
  private getErrorContext(): any {
    try {
      // Try to get game state from localStorage
      const gameState = localStorage.getItem('gameState');
      return {
        gameState: gameState ? JSON.parse(gameState) : null,
        url: window.location.href,
        timestamp: new Date().toISOString(),
      };
    } catch (e) {
      return {
        url: window.location.href,
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * Reset error boundary and retry rendering
   */
  private resetErrorBoundary = (): void => {
    const { retryCount } = this.state;

    // Check if we've exceeded max retries
    if (retryCount >= this.maxRetries) {
      console.warn('Max retry attempts reached. Please reload the page.');
      return;
    }

    // Reset state and increment retry count
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: '',
      retryCount: retryCount + 1,
    });
  };

  /**
   * Reload the entire page
   */
  private reloadPage = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasError, error, errorInfo, errorId, retryCount } = this.state;
    const { children, fallback: FallbackComponent } = this.props;

    // If no error, render children normally
    if (!hasError || !error) {
      return children;
    }

    // Check if max retries exceeded
    const maxRetriesExceeded = retryCount >= this.maxRetries;

    // Prepare fallback props
    const fallbackProps: ErrorFallbackProps = {
      error,
      errorInfo,
      errorId,
      onRetry: maxRetriesExceeded
        ? this.reloadPage
        : this.resetErrorBoundary,
      onReload: this.reloadPage,
      isAppLevel: this.props.isAppLevel,
    };

    // Render custom fallback or default ErrorFallback
    if (FallbackComponent) {
      return <FallbackComponent {...fallbackProps} />;
    }

    return <ErrorFallback {...fallbackProps} />;
  }
}

/**
 * Hook-based API for using error boundaries (for convenience)
 * Note: This doesn't replace the class component, but provides a declarative API
 */
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
): React.FC<P> => {
  const WrappedComponent: React.FC<P> = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name || 'Component'})`;

  return WrappedComponent;
};
