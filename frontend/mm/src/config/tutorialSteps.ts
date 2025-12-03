import type { MMTutorialProgress } from '@crowdcraft/api/types.ts';

export interface TutorialStep {
  id: MMTutorialProgress;
  title: string;
  message: string;
  target?: string; // CSS selector for element to highlight
  position?: 'top' | 'bottom' | 'left' | 'right';
  action?: 'click' | 'wait';
  nextStep?: MMTutorialProgress;
  showSkip?: boolean;
  showBack?: boolean;
}

export const TUTORIAL_STEPS: Record<MMTutorialProgress, TutorialStep | null> = {
  not_started: null,

  welcome: {
    id: 'welcome',
    title: 'Welcome to MemeMint!',
    message: `MemeMint is an asynchronous meme-caption battler:

• Pay 5 MC to see one image with five captions and vote for your favorite
• The winning caption pays its author (and the parent author if it is a riff); voters can also earn bonuses
• After voting, you can post an original caption or riff that joins future rounds

Here is a quick tour so you know how to play and earn MemeCoins.`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your main hub. From here you can:

• Check your wallet and claim the 100 MC daily bonus starting day two
• Join a round for 5 MC to vote on five captions for one image; your entry funds the winning caption payout
• Review finished rounds, track your earnings, and remember your first caption each UTC day is free

Next we will look at how you add a caption after you vote.`,
    target: '.tutorial-dashboard',
    position: 'top',
    nextStep: 'prompt_round',
    showSkip: false,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Add Your Caption',
    message: `After you vote, you can submit a caption for the meme.

• Keep it short and natural — a quick 2–5 word idea that fits the image
• Avoid private info or proper names
• Share an original caption or riff on one you saw; your first caption each UTC day is free

Your caption will appear in future rounds for other players to vote on.`,
    target: '.tutorial-prompt-input',
    position: 'top',
    // The tutorial pauses while you write your first caption.
    nextStep: 'copy_round',
    showSkip: false,
    showBack: true,
  },

  copy_round: {
    id: 'copy_round',
    title: 'Riffing on Captions',
    message: `You can also riff on an existing caption instead of starting from scratch.

• Stay close to the parent caption while putting your own spin on it
• Keep it brief and readable — just a few words that fit the image
• Do not copy the caption exactly or go off-topic

If your riff wins, the base payout is shared between you and the parent caption's author.`,
    target: '.tutorial-copy-input',
    position: 'top',
    // The tutorial resumes after you submit your first riff.
    nextStep: 'vote_round',
    showSkip: false,
    showBack: true,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Vote and Earn',
    message: `Each round shows you one image and five captions you have not seen yet.

• Pay the 5 MC entry fee, then pick your favorite caption
• The entry fee becomes the base payout for the chosen caption's author (and parent if it is a riff)
• The system can also award voter bonuses, so choose carefully

After you vote, you can see the results and decide whether to submit your own caption.`,
    target: '.tutorial-vote-options',
    position: 'top',
    // The tutorial will resume after you finish your first guess.
    nextStep: 'rounds_guide',
    showSkip: false,
    showBack: true,
  },

  rounds_guide: {
    id: 'rounds_guide',
    title: 'Keep Playing for Rewards',
    message: `You are ready to play on your own.

• Claim your daily bonus to keep your wallet stocked
• Use your free daily caption, then keep entering rounds to vote and earn
• Submit originals or riffs so your captions can win future rounds

Images and captions stay active (low performers get retired), so you can refine ideas over time without seeing the same caption
twice.`,
    target: 'div.fixed.bottom-5',
    position: 'top',
    // No nextStep - this is the final tutorial screen, shows "End Tutorial" button
    showSkip: false,
    showBack: true,
  },

  completed: null,
};

export const getTutorialStep = (progress: MMTutorialProgress): TutorialStep | null => {
  return TUTORIAL_STEPS[progress];
};

export const getNextStep = (currentStep: MMTutorialProgress): MMTutorialProgress | null => {
  const step = TUTORIAL_STEPS[currentStep];
  return step?.nextStep || null;
};

export const getPreviousStep = (currentStep: MMTutorialProgress): MMTutorialProgress | null => {
  const steps: MMTutorialProgress[] = ['welcome', 'dashboard', 'prompt_round', 'copy_round', 'vote_round', 'rounds_guide'];
  const currentIndex = steps.indexOf(currentStep);
  if (currentIndex > 0) {
    return steps[currentIndex - 1];
  }
  return null;
};
