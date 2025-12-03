import { TutorialContextConfig } from '@crowdcraft/contexts/TutorialContext';
import type { MMTutorialStatus } from '@crowdcraft/api/types.ts';
import { getNextStep } from '../tutorialSteps';

export const tutorialConfig: TutorialContextConfig<MMTutorialStatus> = {
  mapLoadStatus: (response: unknown) => {
    const typed = response as { tutorial_status?: MMTutorialStatus } | null;
    return typed?.tutorial_status ?? null;
  },
  mapUpdateStatus: (response: unknown) => {
    const typed = response as { tutorial_status: MMTutorialStatus };
    return typed.tutorial_status;
  },
  mapResetStatus: (response: unknown) => response as MMTutorialStatus,
  getProgress: (status: MMTutorialStatus) => status.tutorial_progress,
  isCompleted: (status: MMTutorialStatus) => status.tutorial_completed,
  getNextStep,
};
