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
    position: 'right',
    nextStep: 'prompt_round',
    showSkip: true,
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
    nextStep: 'copy_round', // Changed from 'prompt_round_paused' to 'copy_round'
    showSkip: true,
    showBack: true,
  },

  prompt_round_paused: null,

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
    action: 'wait',
    nextStep: 'vote_round',
    showSkip: true,
    showBack: true,
  },

  copy_round_paused: null,

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
    action: 'wait',
    nextStep: 'completed_rounds_guide',
    showSkip: true,
    showBack: true,
  },

  completed_rounds_guide: {
    id: 'completed_rounds_guide',
    title: 'Explore Past Rounds',
    message: `**Not sure you fully understand the game yet?**

You can click the {{icon:completed}} in the header anytime to view completed rounds and observe how actual past games played out.

This is a great way to learn strategies and see examples of creative quips, convincing copies, and tricky votes!`,
    target: '.tutorial-completed-icon',
    position: 'bottom',
    action: 'wait',
    // No nextStep - this is the final tutorial screen, shows "End Tutorial" button
    showSkip: false,
    showBack: false,
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
  const steps: TutorialProgress[] = ['welcome', 'dashboard', 'prompt_round', 'prompt_round_paused', 'copy_round', 'vote_round', 'completed_rounds_guide'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
