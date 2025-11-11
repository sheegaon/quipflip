import React, { useCallback, useEffect, useState } from 'react';
import { GameProvider, useGame } from './GameContext';
import { QuestProvider } from './QuestContext';
import { TutorialProvider, useTutorial } from './TutorialContext';
import { ResultsProvider, useResults } from './ResultsContext';
import { NetworkProvider } from './NetworkContext';
import { gameContextLogger } from '../utils/logger';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PageErrorFallback } from '../components/ErrorFallback';

// Helper component to reduce ErrorBoundary boilerplate
const ContextErrorBoundary: React.FC<{ children: React.ReactNode; contextName: string }> = ({ children, contextName }) => (
  <ErrorBoundary
    fallback={PageErrorFallback}
    onError={(error, _errorInfo, errorId) => {
      gameContextLogger.error(`${contextName} error caught:`, errorId);
      console.error(error);
    }}
  >
    {children}
  </ErrorBoundary>
);

// Inner component that has access to GameContext
const ContextBridge: React.FC<{
  children: React.ReactNode;
  onDashboardTrigger: () => void;
  dashboardRefreshToken: number;
}> = ({ children, onDashboardTrigger, dashboardRefreshToken }) => {
  const {
    state: gameState,
    actions: { refreshDashboard, refreshBalance },
  } = useGame();
  const { actions: resultsActions } = useResults();
  const { refreshStatus } = useTutorial();

  // Sync pending results to ResultsContext when they change
  React.useEffect(() => {
    gameContextLogger.debug('🔄 Syncing pending results to ResultsContext:', {
      count: gameState.pendingResults.length
    });
    resultsActions.setPendingResults(gameState.pendingResults);
  }, [gameState.pendingResults]); // Remove resultsActions from dependency array

  useEffect(() => {
    refreshStatus({ showLoading: false }).catch((err) => {
      gameContextLogger.error('❌ Failed to refresh tutorial status after auth change', err);
    });
  }, [gameState.isAuthenticated, refreshStatus]);

  useEffect(() => {
    if (dashboardRefreshToken === 0) {
      return;
    }

    const abortController = new AbortController();
    gameContextLogger.debug('🔄 ContextBridge processing dashboard trigger', {
      dashboardRefreshToken,
    });

    const refreshData = async () => {
      try {
        gameContextLogger.debug('📊 Refreshing dashboard data after trigger');
        await refreshDashboard(abortController.signal);
      } catch (err) {
        if (!abortController.signal.aborted) {
          gameContextLogger.error('❌ Failed to refresh dashboard after trigger', err);
        }
      }

      try {
        gameContextLogger.debug('💰 Refreshing balance data after trigger');
        await refreshBalance(abortController.signal);
      } catch (err) {
        if (!abortController.signal.aborted) {
          gameContextLogger.error('❌ Failed to refresh balance after trigger', err);
        }
      }
    };

    refreshData();

    return () => {
      gameContextLogger.debug('🛑 Cleaning up dashboard trigger effect', {
        dashboardRefreshToken,
      });
      abortController.abort();
    };
  }, [dashboardRefreshToken, refreshDashboard, refreshBalance]);

  return (
    <QuestProvider
      isAuthenticated={gameState.isAuthenticated}
      onDashboardTrigger={onDashboardTrigger}
    >
      {children}
    </QuestProvider>
  );
};

export const AppProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dashboardRefreshToken, setDashboardRefreshToken] = useState(0);

  const handleDashboardTrigger = useCallback(() => {
    gameContextLogger.debug('🔄 Dashboard trigger requested from child contexts');
    setDashboardRefreshToken((token) => token + 1);
  }, []);

  return (
    <ContextErrorBoundary contextName="ContextProviders">
      <NetworkProvider>
        <TutorialProvider>
          <ContextErrorBoundary contextName="GameProvider">
            <GameProvider
              onDashboardTrigger={handleDashboardTrigger}
            >
              <InnerProviders
                onDashboardTrigger={handleDashboardTrigger}
                dashboardRefreshToken={dashboardRefreshToken}
              >
                {children}
              </InnerProviders>
            </GameProvider>
          </ContextErrorBoundary>
        </TutorialProvider>
      </NetworkProvider>
    </ContextErrorBoundary>
  );
};

// Component that wraps contexts needing access to GameContext
const InnerProviders: React.FC<{
  children: React.ReactNode;
  onDashboardTrigger: () => void;
  dashboardRefreshToken: number;
}> = ({ children, onDashboardTrigger, dashboardRefreshToken }) => {
  const { state: gameState } = useGame();

  return (
    <ResultsProvider isAuthenticated={gameState.isAuthenticated}>
      <ContextBridge
        onDashboardTrigger={onDashboardTrigger}
        dashboardRefreshToken={dashboardRefreshToken}
      >
        {children}
      </ContextBridge>
    </ResultsProvider>
  );
};