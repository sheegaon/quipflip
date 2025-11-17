import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { tutorialAPI } from '../api/client';
import type { TutorialProgress, TutorialStatus } from '../api/types';
import { tutorialLogger } from '../utils/logger';
import { getNextStep } from '../config/tutorialSteps';
import { getErrorMessage } from '../utils/errorHelpers';

const isAbortError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'AbortError' || maybeError.code === 'ERR_CANCELED';
};

const getActionErrorMessage = (action: string, error: unknown) =>
  getErrorMessage(error, `Failed to ${action.replace(/-/g, ' ')}`);

export type TutorialLifecycleStatus = 'loading' | 'inactive' | 'active' | 'completed' | 'error';

interface TutorialContextState {
  status: TutorialStatus | null;
  tutorialStatus: TutorialLifecycleStatus;
  isActive: boolean;
  currentStep: TutorialProgress | null;
  loading: boolean;
  error: string | null;
}

interface RefreshOptions {
  signal?: AbortSignal;
  showLoading?: boolean;
}

interface TutorialActions {
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: TutorialProgress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: (options?: RefreshOptions) => Promise<void>;
}

interface TutorialContextType extends TutorialContextState {
  state: TutorialContextState;
  actions: TutorialActions;
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: TutorialProgress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: (options?: RefreshOptions) => Promise<void>;
}

const TutorialContext = createContext<TutorialContextType | undefined>(undefined);

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<TutorialStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    [status],
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

  const refreshStatus = useCallback(
    async (options: RefreshOptions = {}) => {
      const { signal, showLoading = true } = options;
      if (showLoading) {
        setLoading(true);
      }
      try {
        tutorialLogger.debug('Fetching tutorial status from backend');
        const data = await tutorialAPI.getTutorialStatus(signal);
        setStatus(data);
        setError(null);
      } catch (err: unknown) {
        if (isAbortError(err)) {
          tutorialLogger.debug('Tutorial status request aborted');
          return;
        }
        const message = getActionErrorMessage('load-tutorial-status', err);
        tutorialLogger.error('Failed to load tutorial status', err);
        setError(message);
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [],
  );

  const updateProgress = useCallback(
    async (progress: TutorialProgress) => {
      setLoading(true);
      try {
        tutorialLogger.debug('Updating tutorial progress', { progress });
        const response = await tutorialAPI.updateTutorialProgress(progress);
        setStatus(response.tutorial_status);
        setError(null);
      } catch (err: unknown) {
        const message = getActionErrorMessage('update-tutorial-progress', err);
        tutorialLogger.error('Failed to update tutorial progress', err);
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const startTutorial = useCallback(async () => {
    tutorialLogger.debug('Starting tutorial');
    await updateProgress('welcome');
  }, [updateProgress]);

  const completeTutorial = useCallback(async () => {
    tutorialLogger.debug('Completing tutorial');
    await updateProgress('completed');
  }, [updateProgress]);

  const advanceStep = useCallback(
    async (stepId?: TutorialProgress) => {
      const nextStep = stepId ?? (status ? getNextStep(status.tutorial_progress) ?? undefined : undefined);

      if (!nextStep) {
        tutorialLogger.debug('No next tutorial step available', {
          current: status?.tutorial_progress ?? 'none',
        });
        return;
      }

      if (nextStep === 'completed') {
        await completeTutorial();
        return;
      }

      await updateProgress(nextStep);
    },
    [status, completeTutorial, updateProgress],
  );

  const skipTutorial = useCallback(async () => {
    tutorialLogger.debug('Skipping tutorial');
    await completeTutorial();
  }, [completeTutorial]);

  const resetTutorial = useCallback(async () => {
    setLoading(true);
    try {
      tutorialLogger.debug('Resetting tutorial via backend');
      const data = await tutorialAPI.resetTutorial();
      setStatus(data);
      setError(null);
    } catch (err: unknown) {
      const message = getActionErrorMessage('reset-tutorial', err);
      tutorialLogger.error('Failed to reset tutorial', err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refreshStatus({ signal: controller.signal });
    return () => controller.abort();
  }, [refreshStatus]);

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

  const actions: TutorialActions = useMemo(
    () => ({
      startTutorial,
      advanceStep,
      skipTutorial,
      completeTutorial,
      resetTutorial,
      refreshStatus,
    }),
    [startTutorial, advanceStep, skipTutorial, completeTutorial, resetTutorial, refreshStatus],
  );

  const value = useMemo<TutorialContextType>(
    () => ({
      ...state,
      state,
      actions,
      startTutorial: actions.startTutorial,
      advanceStep: actions.advanceStep,
      skipTutorial: actions.skipTutorial,
      completeTutorial: actions.completeTutorial,
      resetTutorial: actions.resetTutorial,
      refreshStatus: actions.refreshStatus,
    }),
    [state, actions],
  );

  return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useTutorial = (): TutorialContextType => {
  const context = useContext(TutorialContext);
  if (!context) {
    throw new Error('useTutorial must be used within a TutorialProvider');
  }
  return context;
};
