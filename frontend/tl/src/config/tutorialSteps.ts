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
    message: `ThinkLink is a word-matching game where you guess answers that others have given.

• Guess words and phrases that match what the crowd is thinking
• Higher coverage (more matches) = bigger payouts
• But watch out: 3 wrong guesses and your round ends

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

• Check your wallet (earnings) and vault (long-term savings)
• Start a new round (costs 100 coins)
• View your round history and statistics

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
    message: `In each round:

• You're shown a prompt (like "Things you keep in your pocket")
• You have unlimited guesses—type your answers and submit
• Green = match! You found an answer the crowd gave
• Red = no match and a strike. Get 3 strikes and your round ends
• Higher coverage % = bigger rewards at the end

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
    message: `After your round ends (or you click abandon), you'll see your results:

• Coverage % = how many of the crowd's answers you matched
• Higher coverage % = higher payout (up to 300 coins)
• 30% coverage or less? You keep the full gross payout
• More than 30%? The house takes 30% for the vault

Keep playing and improving your coverage to earn more!`,
    position: 'top',
    nextStep: 'strategy',
    showSkip: false,
    showBack: true,
  },

  strategy: {
    id: 'strategy',
    title: 'Pro Tips',
    message: `• Think about common, everyday answers—not obscure ones
• Pay attention to the prompt's context and wording
• If you're getting strikes, try broader or more obvious answers
• Watch your coverage bar to see how you're doing in real time
• Check the statistics page to track your best and worst prompts

You're all set! Go make your best guesses.`,
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
