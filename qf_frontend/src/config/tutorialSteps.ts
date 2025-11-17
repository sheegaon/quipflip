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
    title: 'Welcome to Quipflip!',
    message: `Quipflip is a creative word game where you'll write quips, copy phrases, and vote on the best matches.

Let's take a quick tour to show you how to play and earn some flipcoins!`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your game dashboard. Here you can:

• See your balance and claim daily bonuses
• View your active rounds and pending results
• Start new rounds to earn coins

Let's start with a **Prompt Round** where you'll create a creative fill-in-the-blank challenge.`,
    target: '.tutorial-dashboard',
    nextStep: 'prompt_round',
    showSkip: false,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Answer a Prompt',
    message: `In a Prompt Round, you answer a fill-in-the-blank sentence, or a *quip*.

For example: "The best pizza topping is ______"

You might try writing "peppers and mushrooms" or "green and black olives".

Then other players will try to write similar quips based on yours, but *without seeing the prompt*. The more uniquely your answer fits the prompt, the more coins you can earn!`,
      // **Click "Next" to start your first Prompt Round.** The tutorial will resume when you finish.
    target: '.tutorial-prompt-round',
    position: 'bottom',
    nextStep: 'copy_round',
    showSkip: false,
    showBack: true,
  },

  copy_round: {
    id: 'copy_round',
    title: 'Write a Copy',
      // Great job! Now let's try a **Copy Round**.
    message: `In a Copy Round, you'll see another player's response to a prompt *without seeing the original prompt*.

Your job is to write a phrase that could blend in with the original. Make it convincing!

Voters will try to identify the original, so the better you match the style, the more you earn.`,
      // **Click "Next" to start a Copy Round.** The tutorial will resume when you finish.
    target: '.tutorial-copy-round',
    position: 'bottom',
    nextStep: 'vote_round',
    showSkip: false,
    showBack: true,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Vote for the Original',
      // Excellent!
    message: `The final type of round is **Voting**.

You'll see a prompt and three phrases. One is the original, two are copies.

Your goal is to identify which phrase was the original. Choose carefully - correct votes earn coins!`,
      // **Make your vote now to complete the tutorial.**
    target: '.tutorial-vote-round',
    position: 'top',
    nextStep: 'rounds_guide',
    showSkip: false,
    showBack: true,
  },

  rounds_guide: {
    id: 'rounds_guide',
    title: 'Practice Makes Perfect!',
    message: `Ready to play on your own?

**Try practice mode first** to get comfortable with the game without risking coins. Use the toggle at the bottom of the dashboard to switch between Live and Practice modes.

When you're ready, switch to Live Mode and start earning coins! You can always come back to practice to refine your strategy.`,
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
