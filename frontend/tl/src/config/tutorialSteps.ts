import type { TutorialProgress } from '@/api/types';

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
    message: `Quipflip is a three-phase bluffing game played with Flipcoins (FC):

• Create an original prompt
• Write clever copies that feel like the original
• Vote to spot the real one and earn rewards

Take this quick tour to see how rounds work and where to earn.`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your home base. From here you can:

• Check your wallet and vault balances and claim the 100 FC daily bonus (starting day two)
• Start a prompt round to write a fresh idea or hop into copy and vote rounds already in progress
• Review finished rounds, collect prizes, and track earnings

Next up: writing a prompt that copycats will chase.`,
    target: '.tutorial-dashboard',
    position: 'top',
    nextStep: 'prompt_round',
    showSkip: false,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Write the Original Prompt',
    message: `Spend Flipcoins to submit a short, punchy prompt other players will try to imitate.

• Keep it concise (a short sentence or phrase)
• Avoid private info or offensive language
• Clear, vivid prompts attract better copies and votes

When two copies arrive, your prompt enters a voting round.`,
    target: '.tutorial-prompt-input',
    position: 'top',
    // The tutorial will pause while you complete your first prompt round.
    nextStep: 'copy_round',
    showSkip: false,
    showBack: true,
  },

  copy_round: {
    id: 'copy_round',
    title: 'Craft a Convincing Copy',
    message: `Copy rounds challenge you to mimic someone else's prompt without matching it exactly.

• Stay on-topic and mirror the style of the original
• Keep it tight and readable—brief phrasing wins
• Avoid exact duplicates or obviously off-topic jokes

If your copy fools voters, you share the prize pool with the original author.`,
    target: '.tutorial-copy-input',
    position: 'top',
    // The tutorial will resume after you submit your first copy.
    nextStep: 'vote_round',
    showSkip: false,
    showBack: true,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Vote to Find the Original',
    message: `Voting rounds show one prompt plus two copies. Your job is to spot the original.

• Pay the vote entry fee, then choose the prompt you think is real
• Correct votes pay a reward and shrink the prize pool shared by creators
• Results appear after you vote so you can learn what fooled the crowd

After voting, keep playing or check your rewards.`,
    target: '.tutorial-vote-options',
    position: 'top',
    nextStep: 'rounds_guide',
    showSkip: false,
    showBack: true,
  },

  rounds_guide: {
    id: 'rounds_guide',
    title: 'Keep the Streak Going',
    message: `You now know the loop:

• Claim daily bonuses to stay funded
• Rotate between prompt, copy, and vote rounds to grow your wallet
• Vault skims a share of profits automatically so leaderboard gains stick

Check your history, refine your style, and keep climbing.`,
    target: 'div.fixed.bottom-5',
    position: 'top',
    // Final tutorial screen
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
