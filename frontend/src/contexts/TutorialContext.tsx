import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';

export type TutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'prompt_round'
  | 'copy_round'
  | 'vote_round'
  | 'completed';

interface TutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: TutorialProgress;
  tutorial_started_at: string | null;
  tutorial_completed_at: string | null;
}

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
  const [tutorialStatus, setTutorialStatus] = useState<TutorialStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<TutorialStatus>('/api/players/tutorial/status');
      setTutorialStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch tutorial status:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateProgress = useCallback(async (progress: TutorialProgress) => {
    try {
      setLoading(true);
      const response = await apiClient.post<{ tutorial_status: TutorialStatus }>(
        '/api/players/tutorial/progress',
        { progress }
      );
      setTutorialStatus(response.data.tutorial_status);
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

  const completeTutorial = useCallback(async () => {
    await updateProgress('completed');
  }, [updateProgress]);

  const skipTutorial = useCallback(async () => {
    await updateProgress('completed');
  }, [updateProgress]);

  const resetTutorial = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.post<TutorialStatus>('/api/players/tutorial/reset', {});
      setTutorialStatus(response.data);
    } catch (error) {
      console.error('Failed to reset tutorial:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Load tutorial status on mount
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

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
