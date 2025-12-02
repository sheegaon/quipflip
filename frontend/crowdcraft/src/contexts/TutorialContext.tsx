/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import apiClient from '@/api/client';
import { getActionErrorMessage } from '@crowdcraft/utils/errorMessages.ts';
import { tutorialLogger } from '@crowdcraft/utils/logger.ts';
import type { TutorialProgress, TutorialStatus } from '@crowdcraft/api/types.ts';
import { getNextStep } from '@crowdcraft/config/tutorialSteps.ts';

const isAbortError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'AbortError' || maybeError.code === 'ERR_CANCELED';
};

export type TutorialLifecycleStatus = 'loading' | 'inactive' | 'active' | 'completed' | 'error';

interface TutorialContextState<Status extends TutorialStatus> {
  status: Status | null;
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

interface TutorialActions<Status extends TutorialStatus> {
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: TutorialProgress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: (options?: RefreshOptions) => Promise<void>;
}

interface TutorialContextType<Status extends TutorialStatus> extends TutorialContextState<Status> {
  state: TutorialContextState<Status>;
  actions: TutorialActions<Status>;
  startTutorial: () => Promise<void>;
  advanceStep: (stepId?: TutorialProgress) => Promise<void>;
  skipTutorial: () => Promise<void>;
  completeTutorial: () => Promise<void>;
  resetTutorial: () => Promise<void>;
  refreshStatus: (options?: RefreshOptions) => Promise<void>;
}

export interface TutorialContextConfig<Status extends TutorialStatus> {
  mapLoadStatus: (response: unknown) => Status | null;
  mapUpdateStatus: (response: unknown) => Status;
  mapResetStatus: (response: unknown) => Status;
  getProgress: (status: Status) => TutorialProgress;
  isCompleted: (status: Status) => boolean;
}

interface TutorialProviderProps<Status extends TutorialStatus> {
  children: React.ReactNode;
  config: TutorialContextConfig<Status>;
}

export const createTutorialContext = <Status extends TutorialStatus>() => {
  const TutorialContext = createContext<TutorialContextType<Status> | undefined>(undefined);

  const TutorialProvider: React.FC<TutorialProviderProps<Status>> = ({ children, config }) => {
    const [status, setStatus] = useState<Status | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const currentStep = useMemo<TutorialProgress | null>(() => {
      if (!status) return null;
      const progress = config.getProgress(status);
      if (progress === 'not_started' || progress === 'completed') {
        return null;
      }
      return progress;
    }, [config, status]);

    const isActive = useMemo(
      () => Boolean(status && !config.isCompleted(status) && config.getProgress(status) !== 'not_started'),
      [config, status],
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
      if (config.getProgress(status) === 'not_started') {
        return 'inactive';
      }
      return 'active';
    }, [status, loading, error, config]);

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
          const data = await apiClient.getTutorialStatus(signal);
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
      async (progress: TutorialProgress) => {
        const token = await ensureToken();
        if (!token) {
          return;
        }

        setLoading(true);
        try {
          tutorialLogger.debug('Updating tutorial progress', { progress });
          const response = await apiClient.updateTutorialProgress(progress);
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
      await updateProgress('welcome');
    }, [updateProgress]);

    const completeTutorial = useCallback(async () => {
      tutorialLogger.debug('Completing tutorial');
      await updateProgress('completed');
    }, [updateProgress]);

    const advanceStep = useCallback(
      async (stepId?: TutorialProgress) => {
        const nextStep = stepId ?? (status ? getNextStep(config.getProgress(status)) ?? undefined : undefined);

        if (!nextStep) {
          tutorialLogger.debug('No next tutorial step available', {
            current: status ? config.getProgress(status) : 'none',
          });
          return;
        }

        if (nextStep === 'completed') {
          await completeTutorial();
          return;
        }

        await updateProgress(nextStep);
      },
      [status, completeTutorial, updateProgress, config],
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
        const data = await apiClient.resetTutorial();
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

    const state: TutorialContextState<Status> = useMemo(
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

    const actions: TutorialActions<Status> = useMemo(
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

    const value = useMemo<TutorialContextType<Status>>(
      () => ({
        ...state,
        state,
        actions,
        startTutorial,
        advanceStep,
        skipTutorial,
        completeTutorial,
        resetTutorial,
        refreshStatus,
      }),
      [state, actions, startTutorial, advanceStep, skipTutorial, completeTutorial, resetTutorial, refreshStatus],
    );

    return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
  };

  const useTutorial = (): TutorialContextType<Status> => {
    const context = useContext(TutorialContext);
    if (!context) {
      throw new Error('useTutorial must be used within TutorialProvider');
    }
    return context;
  };

  return { TutorialProvider, useTutorial };
};
