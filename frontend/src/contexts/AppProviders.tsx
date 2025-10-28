import React, { useCallback, useEffect } from 'react';
import { GameProvider, useGame } from './GameContext';
import { QuestProvider } from './QuestContext';
import { TutorialProvider, useTutorial } from './TutorialContext';
import { ResultsProvider, useResults } from './ResultsContext';
import { gameContextLogger } from '../utils/logger';

// Inner component that has access to GameContext
const ContextBridge: React.FC<{
  children: React.ReactNode;
  onDashboardTrigger: () => void;
}> = ({ children, onDashboardTrigger }) => {
  const { state: gameState } = useGame();
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
  const handleDashboardTrigger = useCallback(() => {
    gameContextLogger.debug('🔄 Dashboard trigger requested from child contexts');
    // This could trigger additional refresh logic if needed
  }, []);

  return (
    <TutorialProvider>
      <GameProvider 
        onDashboardTrigger={handleDashboardTrigger}
      >
        <InnerProviders onDashboardTrigger={handleDashboardTrigger}>
          {children}
        </InnerProviders>
      </GameProvider>
    </TutorialProvider>
  );
};

// Component that wraps contexts needing access to GameContext
const InnerProviders: React.FC<{ 
  children: React.ReactNode;
  onDashboardTrigger: () => void;
}> = ({ children, onDashboardTrigger }) => {
  const { state: gameState } = useGame();

  return (
    <ResultsProvider isAuthenticated={gameState.isAuthenticated}>
      <ContextBridge onDashboardTrigger={onDashboardTrigger}>
        {children}
      </ContextBridge>
    </ResultsProvider>
  );
};