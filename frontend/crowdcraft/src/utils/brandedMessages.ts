export interface BrandedMessagesConfig {
  gameName: string;
  promptSingular: string;
  promptPlural: string;
  copySingular: string;
  copyPlural: string;
  currencyName: string;
  coinImagePath?: string;
}

const titleCase = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);

export const createBrandedMessages = (config: BrandedMessagesConfig) => {
  const promptTitle = titleCase(config.promptSingular);
  const copyTitle = titleCase(config.copySingular);
  const currencyTitle = titleCase(config.currencyName);

  const successMessages = {
    promptSubmitted: [
      `${promptTitle} submitted!`,
      `Your ${config.promptSingular} is in!`,
      'Submission received!',
      `Your ${config.promptSingular} is recorded!`,
      `${promptTitle} locked in!`,
    ],
    promptSubmittedFeedback: [
      "Let's see what creative fakes emerge!",
      `Other players will try matching your ${config.promptSingular}.`,
      `Looking forward to the impostors!`,
      `Fingers crossed for interesting matches!`,
      `Others will work their magic soon.`,
      `Can't wait to see what happens!`,
      `Let's see the creativity unfold!`,
    ],
    copySubmitted: [
      `${copyTitle} submitted!`,
      `Your ${config.copySingular} is in!`,
      'Submission received!',
      `Your ${config.copySingular} is recorded!`,
      `${copyTitle} locked in!`,
    ],
    copySubmittedFeedback: [
      `Voters will decide if it matches!`,
      `Let's see how voters perceive it.`,
      `Your ${config.copySingular} will be reviewed soon.`,
      `Hope voters see your connection!`,
      `May the voting go your way!`,
      `Let's see if voters find it convincing.`,
      `Good luck with the vote!`,
      `Fingers crossed for your ${config.copySingular}!`,
    ],
    voteSubmitted: [
      'Vote locked in!',
      'Your pick is in!',
      'Choice recorded!',
      'Decision made!',
      "Let's see if you're right!",
    ],
    voteCorrectHeading: [
      'Correct!',
      'You got it!',
      'Spot on!',
      'Perfect!',
      'Nailed it!',
      'Right on!',
    ],
    voteIncorrectHeading: [
      'Not quite this time',
      'Almost there',
      'Not this round',
      'Better luck next time',
      'Keep trying',
      'So close',
    ],
    voteCorrect: [
      `You identified the original ${config.promptSingular}!`,
      'You spotted the real deal!',
      'You nailed it!',
      'Your instincts were spot on!',
      'Great eye for originals!',
      `You saw through the ${config.copyPlural}!`,
      "You're a natural at this!",
    ],
    voteIncorrect: [
      'The original can be tricky!',
      'These can be surprisingly difficult.',
      `The ${config.copyPlural} can be quite convincing.`,
      "You're learning! Every round helps.",
      'The differences can be subtle.',
      `Sometimes the original is well hidden among the ${config.copyPlural}.`,
      'Even experts get fooled sometimes!',
    ],
    bonusClaimed: [
      `${currencyTitle} added to your bank!`,
      `Daily ${config.currencyName} collected!`,
      `${currencyTitle} secured!`,
      'Cha-ching!',
    ],
    prizesClaimed: [
      'Winnings collected!',
      `You banked those ${config.currencyName}!`,
      'Prizes claimed successfully!',
      `Rewards added to your ${config.gameName} wallet!`,
    ],
  } as const;

  const getRandomMessage = (category: keyof typeof successMessages): string => {
    const messages = successMessages[category];
    return messages[Math.floor(Math.random() * messages.length)];
  };

  const loadingMessages = {
    default: `Shuffling the ${config.promptPlural}...`,
    starting: `Preparing your ${config.promptSingular}...`,
    submitting: `${titleCase(config.copySingular)} in progress...`,
    loading: `Loading ${config.promptPlural}...`,
    claiming: `Claiming your ${config.currencyName}...`,
  } as const;

  return {
    config,
    successMessages,
    getRandomMessage,
    loadingMessages,
  };
};

export const quipflipBranding = createBrandedMessages({
  gameName: 'Quipflip',
  promptSingular: 'quip',
  promptPlural: 'quips',
  copySingular: 'fake',
  copyPlural: 'fakes',
  currencyName: 'quips',
});

export const mememintBranding = createBrandedMessages({
  gameName: 'MemeMint',
  promptSingular: 'prompt',
  promptPlural: 'prompts',
  copySingular: 'caption',
  copyPlural: 'captions',
  currencyName: 'coins',
});

