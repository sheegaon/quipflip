import { TutorialContextConfig } from '@crowdcraft/contexts/TutorialContext';
import type { TutorialStatus } from '@crowdcraft/api/types.ts';

export const tutorialConfig: TutorialContextConfig<TutorialStatus> = {
  mapLoadStatus: (response: unknown) => response as TutorialStatus,
  mapUpdateStatus: (response: unknown) => {
    const typed = response as { progress: TutorialStatus['progress']; completed: boolean };
    return {
      progress: typed.progress,
      completed: typed.completed,
      last_updated: new Date().toISOString(),
    } as TutorialStatus;
  },
  mapResetStatus: (response: unknown) => response as TutorialStatus,
  getProgress: (status: TutorialStatus) => (status as { progress: TutorialStatus['progress'] }).progress,
  isCompleted: (status: TutorialStatus) => Boolean((status as { completed?: boolean }).completed),
};
