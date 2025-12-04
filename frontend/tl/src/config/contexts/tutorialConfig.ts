import apiClient from '@crowdcraft/api/client.ts';
import { TutorialContextConfig } from '@crowdcraft/contexts/TutorialContext';
import type { TLTutorialProgress, TLTutorialStatus } from '@crowdcraft/api/types.ts';
import { getNextStep } from '../tutorialSteps';

export const tutorialConfig: TutorialContextConfig<TLTutorialStatus, TLTutorialProgress> = {
  mapLoadStatus: (response: unknown) => {
    const typed = response as TLTutorialStatus | { tutorial_status?: TLTutorialStatus } | null;
    if (typed && 'tutorial_status' in (typed as Record<string, unknown>)) {
      return (typed as { tutorial_status?: TLTutorialStatus }).tutorial_status ?? null;
    }
    return typed as TLTutorialStatus | null;
  },
  mapUpdateStatus: (response: unknown) => {
    const typed = response as { tutorial_status?: TLTutorialStatus } | TLTutorialStatus;
    return (typed as { tutorial_status?: TLTutorialStatus }).tutorial_status ?? (typed as TLTutorialStatus);
  },
  mapResetStatus: (response: unknown) => response as TLTutorialStatus,
  getProgress: (status: TLTutorialStatus) => status.tutorial_progress,
  isCompleted: (status: TLTutorialStatus) => status.tutorial_completed,
  loadStatus: (signal?: AbortSignal) => apiClient.tlGetTutorialStatus(signal),
  updateProgress: (progress: TLTutorialProgress) => apiClient.tlUpdateTutorialProgress(progress),
  resetTutorial: () => apiClient.tlResetTutorial(),
  getNextStep,
  initialStep: 'welcome',
  completedStep: 'completed',
  inactiveStep: 'not_started',
};
