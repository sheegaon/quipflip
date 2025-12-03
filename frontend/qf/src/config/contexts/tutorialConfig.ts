import { QFTutorialContextConfig } from '@crowdcraft/contexts/TutorialContext';
import type { QFTutorialStatus } from '@crowdcraft/api/types.ts';
import { getNextStep } from '../tutorialSteps';

export const tutorialConfig: QFTutorialContextConfig<QFTutorialStatus> = {
  mapLoadStatus: (response: unknown) => {
    const typed = response as { tutorial_status?: QFTutorialStatus } | null;
    return typed?.tutorial_status ?? null;
  },
  mapUpdateStatus: (response: unknown) => {
    const typed = response as { tutorial_status: QFTutorialStatus };
    return typed.tutorial_status;
  },
  mapResetStatus: (response: unknown) => response as QFTutorialStatus,
  getProgress: (status: QFTutorialStatus) => status.tutorial_progress,
  isCompleted: (status: QFTutorialStatus) => status.tutorial_completed,
  getNextStep,
};
