import React from 'react';
import type { ErrorInfo } from 'react';

export interface ErrorFallbackProps {
  error: Error;
  errorInfo: ErrorInfo | null;
  errorId: string;
  onRetry: () => void;
  onReload: () => void;
  isAppLevel?: boolean;
}

/**
 * ErrorFallback UI Component
 * Displays user-friendly error messages when the ErrorBoundary catches an error
 */
export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  errorInfo,
  errorId,
  onRetry,
  onReload,
  isAppLevel = false,
}) => {
  const isDevelopment = import.meta.env.DEV;

  return (
    <div className={`${isAppLevel ? 'min-h-screen' : 'min-h-[400px]'} flex items-center justify-center bg-ccl-navy/5 p-4`}>
      <div className="max-w-2xl w-full bg-white rounded-lg shadow-xl overflow-hidden">
        {/* Header */}
        <div className="bg-red-500 text-white p-6">
          <div className="flex items-center gap-3">
            <div className="text-4xl">⚠️</div>
            <div>
              <h1 className="text-2xl font-bold">Oops! Something went wrong</h1>
              <p className="text-sm text-white/90 mt-1">
                We're sorry for the inconvenience. The application encountered an unexpected error.
              </p>
            </div>
          </div>
        </div>

        {/* Error Details */}
        <div className="p-6 space-y-4">
          {/* User-friendly message */}
          <div className="bg-red-50 border-l-4 border-red-500 p-4">
            <p className="text-sm text-red-800">
              <strong>What happened:</strong> {error.message || 'An unexpected error occurred'}
            </p>
          </div>

          {/* Error ID for support */}
          <div className="bg-gray-50 border border-gray-200 rounded p-4">
            <p className="text-xs text-gray-600 mb-1">Error ID (for support):</p>
            <code className="text-sm font-mono text-gray-800 bg-gray-100 px-2 py-1 rounded select-all">
              {errorId}
            </code>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={onRetry}
              className="flex-1 min-w-[140px] bg-ccl-turquoise hover:bg-ccl-turquoise/90 text-white font-semibold py-3 px-6 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ccl-turquoise focus:ring-offset-2"
            >
              Try Again
            </button>
            <button
              onClick={onReload}
              className="flex-1 min-w-[140px] bg-ccl-navy hover:bg-ccl-navy/90 text-white font-semibold py-3 px-6 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ccl-navy focus:ring-offset-2"
            >
              Reload Page
            </button>
          </div>

          {/* Report Issue link */}
          <div className="text-center">
            <a
              href={`mailto:support@quipflip.com?subject=Error%20Report%20${errorId}&body=Error%20ID:%20${errorId}%0A%0APlease%20describe%20what%20you%20were%20doing%20when%20the%20error%20occurred:`}
              className="text-sm text-ccl-turquoise hover:text-ccl-turquoise/80 underline"
            >
              Report this issue to support
            </a>
          </div>

          {/* Development-only error details */}
          {isDevelopment && (
            <details className="mt-6">
              <summary className="cursor-pointer text-sm font-semibold text-gray-700 hover:text-gray-900 mb-2">
                Developer Information (visible in development only)
              </summary>
              <div className="space-y-3 mt-3">
                {/* Error stack */}
                {error.stack && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1">Stack Trace:</p>
                    <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                      {error.stack}
                    </pre>
                  </div>
                )}

                {/* Component stack */}
                {errorInfo?.componentStack && (
                  <div>
                    <p className="text-xs font-semibold text-gray-600 mb-1">Component Stack:</p>
                    <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                      {errorInfo.componentStack}
                    </pre>
                  </div>
                )}
              </div>
            </details>
          )}

          {/* Helpful tips */}
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4">
            <p className="text-sm text-blue-800">
              <strong>💡 Troubleshooting tips:</strong>
            </p>
            <ul className="text-sm text-blue-700 mt-2 space-y-1 list-disc list-inside">
              <li>Try refreshing the page</li>
              <li>Clear your browser cache and cookies</li>
              <li>Check your internet connection</li>
              <li>If the problem persists, contact support with the error ID above</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Simplified fallback for page-level errors (less intrusive)
 */
export const PageErrorFallback: React.FC<ErrorFallbackProps> = (props) => {
  return <ErrorFallback {...props} isAppLevel={false} />;
};

/**
 * App-level fallback for critical errors (full screen)
 */
export const AppErrorFallback: React.FC<ErrorFallbackProps> = (props) => {
  return <ErrorFallback {...props} isAppLevel={true} />;
};
