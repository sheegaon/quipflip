export interface TutorialStatus<Progress extends string = string> {
  tutorial_completed: boolean;
  tutorial_progress: Progress;
  tutorial_started_at?: string | null;
  tutorial_completed_at?: string | null;
}
