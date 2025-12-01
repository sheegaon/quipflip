import React, { useEffect, useState, useCallback } from 'react';
import { useGame } from '../contexts/GameContext';
import { getContextualErrorMessage } from '../utils/errorMessages';

interface ErrorNotificationProps {
  error?: string;
  onDismiss?: () => void;
  autoHide?: boolean;
  duration?: number;
}

export const ErrorNotification: React.FC<ErrorNotificationProps> = ({ 
  error: propError, 
  onDismiss, 
  autoHide = true, 
  duration = 8000 
}) => {
  const { state, actions } = useGame();
  const { error: contextError } = state;
  const { clearError } = actions;
  
  const error = propError || contextError;
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  const handleDismiss = useCallback(() => {
    setIsExiting(true);
    setTimeout(() => {
      if (onDismiss) {
        onDismiss();
      } else {
        clearError();
      }
      setIsVisible(false);
      setIsExiting(false);
    }, 300);
  }, [onDismiss, clearError]);

  useEffect(() => {
    if (error) {
      setIsVisible(true);
      setIsExiting(false);

      if (autoHide) {
        // Auto-clear error after specified duration
        const timeout = setTimeout(() => {
          handleDismiss();
        }, duration);

        return () => clearTimeout(timeout);
      }
    } else {
      setIsVisible(false);
    }
  }, [error, autoHide, duration, handleDismiss]);

  if (!error || !isVisible) return null;

  const contextualError = getContextualErrorMessage(error);
  const isDismissible = contextualError.retryable;

  // Choose appropriate styling based on error category
  const getErrorStyling = (category: string) => {
    switch (category) {
      case 'network':
        return {
          bgColor: 'bg-orange-500',
          icon: '🌐',
          title: 'Connection Issue'
        };
      case 'auth':
        return {
          bgColor: 'bg-red-500',
          icon: '🔒',
          title: 'Authentication Required'
        };
      case 'game':
        return {
          bgColor: 'bg-quip-orange',
          icon: '🎮',
          title: 'Game Issue'
        };
      case 'account':
        return {
          bgColor: 'bg-quip-turquoise',
          icon: '👤',
          title: 'Account Issue'
        };
      case 'rewards':
        return {
          bgColor: 'bg-yellow-500',
          icon: '🎁',
          title: 'Rewards'
        };
      default:
        return {
          bgColor: 'bg-red-500',
          icon: '⚠️',
          title: 'Error'
        };
    }
  };

  const styling = getErrorStyling(contextualError.category);

  return (
    <div className={`fixed top-4 right-4 z-50 max-w-md transition-all duration-300 ${
      isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'
    }`}>
      <div className={`${styling.bgColor} text-white rounded-lg shadow-lg overflow-hidden`}>
        {/* Progress bar for auto-hide */}
        {autoHide && (
          <div className="h-1 bg-black bg-opacity-20">
            <div 
              className="h-full bg-white bg-opacity-50 transition-all ease-linear"
              style={{ 
                width: '100%',
                animation: `shrink ${duration}ms linear forwards`
              }}
            />
          </div>
        )}
        
        <div className="p-4">
          <div className="flex items-start gap-3">
            <div className="text-xl flex-shrink-0">
              {styling.icon}
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <p className="font-semibold text-sm">{styling.title}</p>
                {isDismissible && (
                  <button
                    onClick={handleDismiss}
                    className="text-white hover:text-gray-200 font-bold text-xl leading-none ml-2 flex-shrink-0"
                    aria-label="Dismiss error"
                  >
                    ×
                  </button>
                )}
              </div>
              
              <p className="text-sm leading-relaxed">{contextualError.message}</p>
              
              {contextualError.suggestion && (
                <p className="text-xs mt-2 text-white text-opacity-90">
                  💡 {contextualError.suggestion}
                </p>
              )}
              
              {/* Action buttons for retryable errors */}
              {contextualError.retryable && contextualError.category === 'network' && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => window.location.reload()}
                    className="text-xs bg-white bg-opacity-20 hover:bg-opacity-30 px-3 py-1 rounded transition-colors"
                  >
                    Retry
                  </button>
                  <button
                    onClick={handleDismiss}
                    className="text-xs text-white text-opacity-70 hover:text-opacity-100 px-3 py-1 transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* CSS animation for progress bar */}
      <style>
        {`
          @keyframes shrink {
            from { width: 100%; }
            to { width: 0%; }
          }
        `}
      </style>
    </div>
  );
};
