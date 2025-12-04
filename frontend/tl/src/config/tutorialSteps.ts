import type { TLTutorialProgress } from '@crowdcraft/api/types.ts';

export interface TutorialStep {
  id: TLTutorialProgress;
  title: string;
  message: string;
  target?: string; // CSS selector for element to highlight
  position?: 'top' | 'bottom' | 'left' | 'right';
  action?: 'click' | 'wait';
  nextStep?: TLTutorialProgress;
  showSkip?: boolean;
  showBack?: boolean;
}

export const TUTORIAL_STEPS: Record<TLTutorialProgress, TutorialStep | null> = {
  not_started: null,

  welcome: {
    id: 'welcome',
    title: 'Welcome to ThinkLink!',
    message: `ThinkLink is a semantic-guessing game.

• Submit short phrases that match what the crowd has already answered
• Each round ends after 3 strikes with unmatched guesses
• Coverage shows how much of the crowd's weighted ideas you've matched

Ready to see how it works? Let's play!`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your home base. From here you can:

• See your wallet and vault balances
• Start a ThinkLink round (snapshot of up to 1000 active answers)
• Review your recent rounds and coverage history

Let's start your first round by clicking the "Start Round" button.`,
    target: '.tutorial-dashboard',
    position: 'top',
    nextStep: 'gameplay',
    showSkip: false,
    showBack: true,
  },

  gameplay: {
    id: 'gameplay',
    title: 'How to Play',
    message: `Each round uses the frozen snapshot for your prompt.

• Submit 2–5 word phrases that stay on-topic and pass moderation
• Every guess is compared to all snapshot answers; a match marks that cluster matched
• No match? You take a strike. Three strikes ends the round, but guesses are unlimited
• You can abandon the round early if you want

Try typing some guesses now!`,
    target: '.tutorial-guess-input',
    position: 'top',
    nextStep: 'scoring',
    showSkip: false,
    showBack: true,
  },

  scoring: {
    id: 'scoring',
    title: 'Earning Your Payout',
    message: `Your score comes from weighted coverage:

• Answers live in clusters; matching any answer marks that cluster as covered
• Popular answers carry more weight, so matching common ideas boosts coverage faster
• The snapshot stays fixed for the round, so you always score against the same set

Higher weighted coverage means a better payout.`,
    position: 'top',
    nextStep: 'strategy',
    showSkip: false,
    showBack: true,
  },

  strategy: {
    id: 'strategy',
    title: 'Pro Tips',
    message: `• Start with obvious, on-topic phrases before exploring niche ideas
• Avoid repeating your own similar guesses—variety helps cover more clusters
• If strikes pile up, back off to broader answers that most people would give
• Remember: new guesses compare against every snapshot answer with a semantic threshold

You're all set! Go make your best matches.`,
    target: '.tutorial-dashboard',
    position: 'top',
    showSkip: false,
    showBack: true,
  },

  completed: null,
};

export const getTutorialStep = (progress: TLTutorialProgress): TutorialStep | null => {
  return TUTORIAL_STEPS[progress];
};

export const getNextStep = (currentStep: TLTutorialProgress): TLTutorialProgress | null => {
  const step = TUTORIAL_STEPS[currentStep];
  return step?.nextStep || null;
};

export const getPreviousStep = (currentStep: TLTutorialProgress): TLTutorialProgress | null => {
  const steps: TLTutorialProgress[] = ['welcome', 'dashboard', 'gameplay', 'scoring', 'strategy'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
