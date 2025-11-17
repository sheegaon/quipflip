import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { TutorialProgress, TutorialStatus } from '../types/tutorial';
import { getNextStep } from '../config/tutorialSteps';

export type TutorialLifecycleStatus = 'loading' | 'inactive' | 'active' | 'completed' | 'error';

interface TutorialContextState {
  status: TutorialStatus | null;
  tutorialStatus: TutorialLifecycleStatus;
  isActive: boolean;
  currentStep: TutorialProgress | null;
  loading: boolean;
  error: string | null;
}

interface TutorialActions {
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: TutorialProgress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
}

interface TutorialContextType extends TutorialContextState, TutorialActions {}

const TUTORIAL_STORAGE_KEY = 'ir_tutorial_status';

const TutorialContext = createContext<TutorialContextType | undefined>(undefined);

const loadStoredStatus = (): TutorialStatus | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = localStorage.getItem(TUTORIAL_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as TutorialStatus;
  } catch (err) {
    console.warn('Failed to parse stored tutorial status', err);
    return null;
  }
};

const persistStatus = (status: TutorialStatus) => {
  localStorage.setItem(TUTORIAL_STORAGE_KEY, JSON.stringify(status));
};

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<TutorialStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = loadStoredStatus();
    if (stored) {
      setStatus(stored);
    }
  }, []);

  const currentStep = useMemo<TutorialProgress | null>(() => {
    if (!status) return null;
    const progress = status.tutorial_progress;
    if (progress === 'not_started' || progress === 'completed') {
      return null;
    }
    return progress;
  }, [status]);

  const isActive = useMemo(
    () => Boolean(status && !status.tutorial_completed && status.tutorial_progress !== 'not_started'),
    [status]
  );

  const lifecycleStatus = useMemo<TutorialLifecycleStatus>(() => {
    if (loading && !status) {
      return 'loading';
    }
    if (error) {
      return 'error';
    }
    if (!status) {
      return 'inactive';
    }
    if (status.tutorial_completed) {
      return 'completed';
    }
    if (status.tutorial_progress === 'not_started') {
      return 'inactive';
    }
    return 'active';
  }, [status, loading, error]);

  const updateStatus = useCallback(async (progress: TutorialProgress) => {
    setLoading(true);
    try {
      const newStatus: TutorialStatus = {
        tutorial_completed: progress === 'completed',
        tutorial_progress: progress,
      };
      setStatus(newStatus);
      persistStatus(newStatus);
      setError(null);
    } catch (err) {
      console.error('Failed to update tutorial progress', err);
      setError('Unable to save tutorial progress');
    } finally {
      setLoading(false);
    }
  }, []);

  const startTutorial = useCallback(async () => {
    await updateStatus('welcome');
  }, [updateStatus]);

  const completeTutorial = useCallback(async () => {
    await updateStatus('completed');
  }, [updateStatus]);

  const advanceStep = useCallback(
    async (stepId?: TutorialProgress) => {
      const nextStep = stepId ?? (status ? getNextStep(status.tutorial_progress) ?? undefined : undefined);

      if (!nextStep) {
        return;
      }

      if (nextStep === 'completed') {
        await completeTutorial();
        return;
      }

      await updateStatus(nextStep);
    },
    [status, completeTutorial, updateStatus],
  );

  const skipTutorial = useCallback(async () => {
    await completeTutorial();
  }, [completeTutorial]);

  const resetTutorial = useCallback(async () => {
    await updateStatus('not_started');
  }, [updateStatus]);

  const state: TutorialContextState = useMemo(
    () => ({
      status,
      tutorialStatus: lifecycleStatus,
      isActive,
      currentStep,
      loading,
      error,
    }),
    [status, lifecycleStatus, isActive, currentStep, loading, error],
  );

  const value: TutorialContextType = useMemo(
    () => ({
      ...state,
      startTutorial,
      advanceStep,
      skipTutorial,
      completeTutorial,
      resetTutorial,
    }),
    [state, startTutorial, advanceStep, skipTutorial, completeTutorial, resetTutorial],
  );

  return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
};

export const useTutorial = (): TutorialContextType => {
  const context = useContext(TutorialContext);
  if (!context) {
    throw new Error('useTutorial must be used within a TutorialProvider');
  }
  return context;
};
