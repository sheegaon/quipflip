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
    title: 'Welcome to MemeMint!',
    message: `MemeMint is a creative caption contest game where you:

• Quip: write the original answer to a prompt
• Impostor: fake the original answer so it blends in
• Guess: pick which answer was written first

We will take a quick tour so you know how to play and earn memecoins.`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your main hub. From here you can:

• See your balance and claim your daily bonus
• Continue active rounds and check results
• Start new rounds as Quip, Impostor, or Guess
• Switch between Practice Mode and Live Mode using the toggle at the bottom

Next we will look at a Quip Round, where you write the original answer.`,
    target: '.tutorial-dashboard',
    position: 'top',
    nextStep: 'prompt_round',
    showSkip: false,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Quip Round: Write the Original',
    message: `In a Quip Round you see a fill-in-the-blank style prompt and write the original answer.

• Keep it short and punchy (around 2–5 words)
• Make it something a normal person might say
• Avoid private info or proper names

Later, other players will only see your answer (not the prompt) in Impostor Rounds and try to write fakes that look like your original.`,
    target: '.tutorial-prompt-input',
    position: 'top',
    // The tutorial will pause while you complete your first Quip Round.
    nextStep: 'copy_round',
    showSkip: false,
    showBack: true,
  },

  copy_round: {
    id: 'copy_round',
    title: 'Impostor Round: Fake the Original',
    message: `In an Impostor Round you do not see the original prompt. You only see another player's answer.

Your job is to write a phrase that could have been the original and might trick voters.

• Do: stay close in meaning, 2–5 words, and keep it natural
• Do: make it sound like a reasonable answer to some prompt
• Do not: repeat the original word for word
• Do not: go totally off-topic or try to guess the hidden prompt literally

If you are stuck, you can tap a suggested phrase and tweak it.`,
    target: '.tutorial-copy-input',
    position: 'top',
    // The tutorial will resume after you submit your first impostor phrase.
    nextStep: 'vote_round',
    showSkip: false,
    showBack: true,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Guess the Original (Vote Round)',
    message: `In a Guess Round you see three phrases:

• One is the original answer
• Two are impostor fakes

Tap the one you think was written first. If you guess the original correctly you earn memecoins. After you vote, you will see which phrase was the original and how everyone voted.`,
    target: '.tutorial-vote-options',
    position: 'top',
    // The tutorial will resume after you finish your first guess.
    nextStep: 'rounds_guide',
    showSkip: false,
    showBack: true,
  },

  rounds_guide: {
    id: 'rounds_guide',
    title: 'Practice Makes Perfect!',
    message: `You are ready to play on your own.

To get comfortable with the game, try Practice Mode:

• Use the mode toggle at the bottom of the screen to switch between Practice and Live
• Practice Mode lets you play rounds without worrying about your main balance
• Live Mode lets you earn and lose memecoins in real games

Experiment in Practice, then switch to Live Mode when you feel confident. You can always return to Practice to refine your strategy.`,
    target: 'div.fixed.bottom-5',
    position: 'top',
    // No nextStep - this is the final tutorial screen, shows "End Tutorial" button
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
  const steps: TutorialProgress[] = ['welcome', 'dashboard', 'prompt_round', 'copy_round', 'vote_round', 'rounds_guide'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
