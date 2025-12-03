import { TutorialContextConfig } from '@crowdcraft/contexts/TutorialContext';
import type { TutorialStatus } from '@crowdcraft/api/types.ts';
import { getNextStep } from '../tutorialSteps';

export const tutorialConfig: TutorialContextConfig<TutorialStatus> = {
  mapLoadStatus: (response: unknown) => {
    const typed = response as { tutorial_status?: TutorialStatus } | null;
    return typed?.tutorial_status ?? null;
  },
  mapUpdateStatus: (response: unknown) => {
    const typed = response as { tutorial_status: TutorialStatus };
    return typed.tutorial_status;
  },
  mapResetStatus: (response: unknown) => response as TutorialStatus,
  getProgress: (status: TutorialStatus) => status.tutorial_progress,
  isCompleted: (status: TutorialStatus) => status.tutorial_completed,
  getNextStep,
};
