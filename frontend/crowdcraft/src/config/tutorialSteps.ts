import type { TutorialProgress } from '@crowdcraft/api/types.ts';

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
    message: `MemeMint is an asynchronous meme-caption battler:

• Pay an entry fee, see one image and five captions, and vote for your favorite
• Winning caption authors get paid in MemeCoins, and voters may earn bonuses
• After voting, you can add your own caption (original or riff) for future rounds

We will take a quick tour so you know how to play and earn MemeCoins.`,
    position: 'bottom',
    nextStep: 'dashboard',
    showSkip: true,
    showBack: false,
  },

  dashboard: {
    id: 'dashboard',
    title: 'Your Dashboard',
    message: `This is your main hub. From here you can:

• See your wallet balance and claim the 100 MC daily bonus (after day one)
• Join a round for 5 MC to vote on five captions for a single image
• Review finished rounds and track your MemeCoin earnings

Next we will look at how you add a caption after you vote.`,
    target: '.tutorial-dashboard',
    position: 'top',
    nextStep: 'prompt_round',
    showSkip: false,
    showBack: true,
  },

  prompt_round: {
    id: 'prompt_round',
    title: 'Write Your Caption',
    message: `After you vote, you can submit a caption for the meme.

• Keep it short and natural — a quick 2–5 word idea that fits the image
• Avoid private info or proper names
• You can post an original caption or riff on one you saw

Your caption will appear in future rounds for other players to vote on.`,
    target: '.tutorial-prompt-input',
    position: 'top',
    // The tutorial will pause while you complete your first Quip Round.
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

If your riff wins a round, both you and the parent caption's author earn MemeCoins.`,
    target: '.tutorial-copy-input',
    position: 'top',
    // The tutorial will resume after you submit your first impostor phrase.
    nextStep: 'vote_round',
    showSkip: false,
    showBack: true,
  },

  vote_round: {
    id: 'vote_round',
    title: 'Vote and Earn',
    message: `Each round shows you one image and five captions from other players.

• Pay the 5 MC entry fee, then pick your favorite caption
• The winning caption earns MemeCoins for its author (and parent if it is a riff)
• The system can also award voter bonuses

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
• Enter rounds to vote on captions and keep earning
• Submit originals or riffs so your captions can win future rounds

Images and captions are replayable, so you can refine your ideas and climb the leaderboard over time.`,
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
