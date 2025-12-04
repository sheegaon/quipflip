/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import apiClient from '../api/client.ts';
import { getActionErrorMessage , tutorialLogger } from '../utils';
import type { TutorialStatus } from '../types/tutorial.ts';
import type { QFTutorialProgress } from '../api/types.ts';

const isAbortError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'AbortError' || maybeError.code === 'ERR_CANCELED';
};

export type TutorialLifecycleStatus = 'loading' | 'inactive' | 'active' | 'completed' | 'error';

interface TutorialContextState<Status extends TutorialStatus<Progress>, Progress extends string> {
  status: Status | null;
  tutorialStatus: TutorialLifecycleStatus;
  isActive: boolean;
  currentStep: Progress | null;
  loading: boolean;
  error: string | null;
}

interface RefreshOptions {
  signal?: AbortSignal;
  showLoading?: boolean;
}

interface TutorialActions<Progress extends string> {
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: Progress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: (options?: RefreshOptions) => Promise<void>;
}

interface TutorialContextType<Status extends TutorialStatus<Progress>, Progress extends string> {
  state: TutorialContextState<Status, Progress>;
  actions: TutorialActions<Progress>;
}

export interface TutorialContextConfig<Status extends TutorialStatus<Progress>, Progress extends string> {
  mapLoadStatus: (response: unknown) => Status | null;
  mapUpdateStatus: (response: unknown) => Status;
  mapResetStatus: (response: unknown) => Status;
  getProgress: (status: Status) => Progress;
  isCompleted: (status: Status) => boolean;
  getNextStep?: (progress: Progress) => Progress | null;
  loadStatus?: (signal?: AbortSignal) => Promise<unknown>;
  updateProgress?: (progress: Progress) => Promise<unknown>;
  resetTutorial?: () => Promise<unknown>;
  initialStep?: Progress;
  completedStep?: Progress;
  inactiveStep?: Progress;
}

interface TutorialProviderProps<Status extends TutorialStatus<Progress>, Progress extends string> {
  children: React.ReactNode;
  config: TutorialContextConfig<Status, Progress>;
}

export const createTutorialContext = <
  Status extends TutorialStatus<Progress>,
  Progress extends string = Status extends TutorialStatus<infer P> ? P : string,
>() => {
  const TutorialContext = createContext<TutorialContextType<Status, Progress> | undefined>(undefined);

  const TutorialProvider: React.FC<TutorialProviderProps<Status, Progress>> = ({ children, config }) => {
    const [status, setStatus] = useState<Status | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const inactiveStep = useMemo(() => config.inactiveStep ?? ('not_started' as Progress), [config]);
    const completedStep = useMemo(() => config.completedStep ?? ('completed' as Progress), [config]);
    const initialStep = useMemo(() => config.initialStep ?? ('welcome' as Progress), [config]);

    const currentStep = useMemo<Progress | null>(() => {
      if (!status) return null;
      const progress = config.getProgress(status);
      if (progress === inactiveStep || progress === completedStep) {
        return null;
      }
      return progress;
    }, [config, status, inactiveStep, completedStep]);

    const isActive = useMemo(
      () => Boolean(status && !config.isCompleted(status) && config.getProgress(status) !== inactiveStep),
      [config, status, inactiveStep],
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
      if (config.isCompleted(status)) {
        return 'completed';
      }
      if (config.getProgress(status) === inactiveStep) {
        return 'inactive';
      }
      return 'active';
    }, [status, loading, error, config, inactiveStep]);

    const ensureToken = useCallback(async (): Promise<string | null> => {
      // Authentication is now handled via cookies
      // Check if user is logged in by looking for stored username
      const username = apiClient.getStoredUsername();
      if (!username) {
        tutorialLogger.debug('No stored username, skipping tutorial API calls');
        return null;
      }
      // If we have a username, cookies should handle authentication
      return 'authenticated';
    }, []);

    const refreshStatus = useCallback(
      async (options: RefreshOptions = {}) => {
        const { signal, showLoading = true } = options;
        if (showLoading) {
          setLoading(true);
        }
        try {
          const token = await ensureToken();
          if (!token) {
            setError(null);
            return;
          }

          tutorialLogger.debug('Fetching tutorial status from backend');
          const data = config.loadStatus
            ? await config.loadStatus(signal)
            : await apiClient.getTutorialStatus(signal);
          setStatus(config.mapLoadStatus(data));
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
      [ensureToken, config],
    );

    const updateProgress = useCallback(
      async (progress: Progress) => {
        const token = await ensureToken();
        if (!token) {
          return;
        }

        setLoading(true);
        try {
          tutorialLogger.debug('Updating tutorial progress', { progress });
          const response = config.updateProgress
            ? await config.updateProgress(progress)
            : await apiClient.updateTutorialProgress(progress as QFTutorialProgress);
          setStatus(config.mapUpdateStatus(response));
          setError(null);
        } catch (err: unknown) {
          const message = getActionErrorMessage('update-tutorial-progress', err);
          tutorialLogger.error('Failed to update tutorial progress', err);
          setError(message);
        } finally {
          setLoading(false);
        }
      },
      [ensureToken, config],
    );

    const startTutorial = useCallback(async () => {
      tutorialLogger.debug('Starting tutorial');
      await updateProgress(initialStep);
    }, [initialStep, updateProgress]);

    const completeTutorial = useCallback(async () => {
      tutorialLogger.debug('Completing tutorial');
      await updateProgress(completedStep);
    }, [completedStep, updateProgress]);

    const advanceStep = useCallback(
      async (stepId?: Progress) => {
        const nextStep =
          stepId ?? (status ? config.getNextStep?.(config.getProgress(status)) ?? undefined : undefined);

        if (!nextStep) {
          tutorialLogger.debug('No next tutorial step available', {
            current: status ? config.getProgress(status) : 'none',
          });
          return;
        }

        if (nextStep === completedStep) {
          await completeTutorial();
          return;
        }

        await updateProgress(nextStep);
      },
      [status, completeTutorial, updateProgress, config, completedStep],
    );

    const skipTutorial = useCallback(async () => {
      tutorialLogger.debug('Skipping tutorial');
      await completeTutorial();
    }, [completeTutorial]);

    const resetTutorial = useCallback(async () => {
      const token = await ensureToken();
      if (!token) {
        return;
      }

      setLoading(true);
      try {
        tutorialLogger.debug('Resetting tutorial via backend');
        const data = config.resetTutorial ? await config.resetTutorial() : await apiClient.resetTutorial();
        setStatus(config.mapResetStatus(data));
        setError(null);
      } catch (err: unknown) {
        const message = getActionErrorMessage('reset-tutorial', err);
        tutorialLogger.error('Failed to reset tutorial', err);
        setError(message);
      } finally {
        setLoading(false);
      }
    }, [ensureToken, config]);

    useEffect(() => {
      const controller = new AbortController();
      refreshStatus({ signal: controller.signal });
      return () => controller.abort();
    }, [refreshStatus]);

    const state: TutorialContextState<Status, Progress> = useMemo(
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

    const actions: TutorialActions<Progress> = useMemo(
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

    const value = useMemo<TutorialContextType<Status, Progress>>(
      () => ({
        state,
        actions,
      }),
      [state, actions],
    );

    return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
  };

  const useTutorial = (): TutorialContextType<Status, Progress> => {
    const context = useContext(TutorialContext);
    if (!context) {
      throw new Error('useTutorial must be used within TutorialProvider');
    }
    return context;
  };

  return { TutorialProvider, useTutorial };
};

// Backwards compatibility exports for legacy QF-named imports
export type QFTutorialContextConfig<Status extends TutorialStatus<Progress>, Progress extends string = Status extends TutorialStatus<infer P> ? P : string> = TutorialContextConfig<Status, Progress>;
export const qfCreateTutorialContext = createTutorialContext;
