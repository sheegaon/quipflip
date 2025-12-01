import type { TutorialProgress } from '../api/types';

export interface TutorialStep {
  id: TutorialProgress;
  title: string;
  message: string;
  target?: string; // CSS selector for element to highlight
  position?: 'top' | 'bottom' | 'left' | 'right';
  action?: 'click' | 'wait';
  nextStep?: TutorialProgress;
  showSkip?: boolean;
  showBack?: boolean;
}

export const TUTORIAL_STEPS: Record<TutorialProgress, TutorialStep | null> = {
  not_started: null,

  welcome: {
    id: 'welcome',
    title: 'Welcome to Initial Reaction!',
    message: `Initial Reaction is a backronym battle. You turn a short word into a clever phrase — one word per letter — and then vote on the best entry.

You'll spend **InitCoins** to enter and can win a share of the prize pool based on votes. Let's take a quick tour!`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Battle Hub',
    message: `This dashboard shows your wallet, vault, and any active battles.

• Tap **Start Backronym Battle** to spend 100 InitCoins and receive a random 3–5 letter word.
• Standard mode waits for humans; Rapid mode fills with AI after short timeouts.
• Daily bonuses help you stay funded.`,
    target: '.tutorial-dashboard',
    nextStep: 'backronym_entry',
    showSkip: false,
    showBack: true,
  },

  backronym_entry: {
    id: 'backronym_entry',
    title: 'Build Your Backronym',
    message: `Create one word for each letter of the prompt word. Keep these rules in mind:

• Words must start with the matching letter and use standard dictionary words.
• Grammar doesn't matter; repeated words are allowed.
• Hit **Validate** to check spelling before you submit.

When you're happy, submit and we'll queue your entry for voting.`,
    target: '.tutorial-backronym-form',
    position: 'bottom',
    nextStep: 'backronym_voting',
    showSkip: false,
    showBack: true,
  },

  backronym_voting: {
    id: 'backronym_voting',
    title: 'Cast Your Vote',
    message: `When voting opens you can choose one favorite backronym. Creators vote for free; non-participants pay 10 InitCoins but earn 20 if they match the crowd.

You can't vote for your own entry. AI voters appear when timers expire to keep results moving.`,
    target: '.tutorial-voting-card',
    position: 'top',
    nextStep: 'rounds_guide',
    showSkip: false,
    showBack: true,
  },

  rounds_guide: {
    id: 'rounds_guide',
    title: 'See Payouts',
    message: `Results split the prize pool among creators based on vote share. Non-participant winnings are paid first, then 30% of each player's net winnings goes to the vault automatically.

From here you can review entries, check your earnings, and start another battle.`,
    target: '.tutorial-results-card',
    position: 'top',
    // End tutorial here
    showSkip: false,
    showBack: true,
  },

  completed: null,
};

export const getTutorialStep = (progress: TutorialProgress): TutorialStep | null => {
  return TUTORIAL_STEPS[progress];
};

export const getNextStep = (currentStep: TutorialProgress): TutorialProgress | null => {
  const step = TUTORIAL_STEPS[currentStep];
  return step?.nextStep || null;
};

export const getPreviousStep = (currentStep: TutorialProgress): TutorialProgress | null => {
  const steps: TutorialProgress[] = ['welcome', 'dashboard', 'backronym_entry', 'backronym_voting', 'rounds_guide'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
