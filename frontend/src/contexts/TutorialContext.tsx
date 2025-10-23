import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import type { TutorialProgress, TutorialStatus } from '../api/types';
import { useGame } from './GameContext';

interface TutorialContextType {
  tutorialStatus: TutorialStatus | null;
  isActive: boolean;
  currentStep: TutorialProgress;
  loading: boolean;

  startTutorial: () => Promise<void>;
  advanceStep: (step: TutorialProgress) => Promise<void>;
  completeTutorial: () => Promise<void>;
  skipTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: () => Promise<void>;
}

const TutorialContext = createContext<TutorialContextType | undefined>(undefined);

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();
  const { isAuthenticated } = state;
  const [tutorialStatus, setTutorialStatus] = useState<TutorialStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.getTutorialStatus();
      setTutorialStatus(data);
    } catch (error) {
      console.error('Failed to fetch tutorial status:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateProgress = useCallback(async (progress: TutorialProgress) => {
    try {
      setLoading(true);
      const response = await apiClient.updateTutorialProgress(progress);
      setTutorialStatus(response.tutorial_status);
    } catch (error) {
      console.error('Failed to update tutorial progress:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  const startTutorial = useCallback(async () => {
    await updateProgress('welcome');
  }, [updateProgress]);

  const advanceStep = useCallback(async (step: TutorialProgress) => {
    await updateProgress(step);
  }, [updateProgress]);

  // Both complete and skip end the tutorial by setting progress to 'completed'
  const completeTutorial = useCallback(async () => {
    await updateProgress('completed');
  }, [updateProgress]);

  // Alias for completeTutorial - semantically clearer when user chooses to skip
  const skipTutorial = completeTutorial;

  const resetTutorial = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.resetTutorial();
      setTutorialStatus(data);
    } catch (error) {
      console.error('Failed to reset tutorial:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Load tutorial status only when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      refreshStatus();
    }
  }, [isAuthenticated, refreshStatus]);

  const isActive = tutorialStatus
    ? !tutorialStatus.tutorial_completed && tutorialStatus.tutorial_progress !== 'not_started'
    : false;

  const currentStep = tutorialStatus?.tutorial_progress || 'not_started';

  return (
    <TutorialContext.Provider
      value={{
        tutorialStatus,
        isActive,
        currentStep,
        loading,
        startTutorial,
        advanceStep,
        completeTutorial,
        skipTutorial,
        resetTutorial,
        refreshStatus,
      }}
    >
      {children}
    </TutorialContext.Provider>
  );
};

export const useTutorial = () => {
  const context = useContext(TutorialContext);
  if (context === undefined) {
    throw new Error('useTutorial must be used within a TutorialProvider');
  }
  return context;
};
