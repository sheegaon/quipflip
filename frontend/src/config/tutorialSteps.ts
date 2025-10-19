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
    title: 'Welcome to QuipFlip!',
    message: `QuipFlip is a creative word game where you'll write prompts, copy phrases, and vote on the best matches.

Let's take a quick tour to show you how to play and earn coins!`,
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
    target: '.tutorial-balance',
    position: 'bottom',
    nextStep: 'prompt_round',
    showSkip: true,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Create a Prompt',
    message: `In a Prompt Round, you create a fill-in-the-blank sentence, or a *quip*.

For example: "The best pizza topping is ______"

You might try writing "peppers and mushrooms" or "green and black olives".

Then other players will try to write similar quips based on yours, but *without seeing the prompt*. The more uniquely your answer fits the prompt, the more coins you can earn!

**Try answering your first prompt now.**`,
    target: '.tutorial-prompt-input',
    position: 'top',
    action: 'wait',
    nextStep: 'copy_round',
    showSkip: true,
    showBack: true,
  },

  copy_round: {
    id: 'copy_round',
    title: 'Write a Copy',
    message: `Great job! Now let's try a **Copy Round**.

In a Copy Round, you'll see a prompt like "The best dessert is ______" with an original answer.

Your job is to write a phrase that could blend in with the original. Make it convincing!

Voters will try to identify the original, so the better you match the style, the more you earn.

**Write your copy phrase now.**`,
    target: '.tutorial-copy-input',
    position: 'top',
    action: 'wait',
    nextStep: 'vote_round',
    showSkip: true,
    showBack: false,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Vote for the Original',
    message: `Excellent! The final type of round is **Voting**.

You'll see a prompt and three phrases. One is the original, two are copies.

Your goal is to identify which phrase was the original. Choose carefully - correct votes earn coins!

**Make your vote now to complete the tutorial.**`,
    target: '.tutorial-vote-options',
    position: 'top',
    action: 'wait',
    nextStep: 'completed',
    showSkip: true,
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
  const steps: TutorialProgress[] = ['welcome', 'dashboard', 'prompt_round', 'copy_round', 'vote_round'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
