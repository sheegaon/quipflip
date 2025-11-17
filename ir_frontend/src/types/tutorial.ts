export type TutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'create_round'
  | 'tracking'
  | 'voting'
  | 'results'
  | 'completed';

export interface TutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: TutorialProgress;
}
