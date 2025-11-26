/**
 * Branded success messages for Quipflip
 */

export const successMessages = {
  promptSubmitted: [
    "Quip submitted!",
    "Your quip is in!",
    "Submission received!",
    "Your quip is recorded!",
    "Phrase locked in!",
  ],
  promptSubmittedFeedback: [
    "Let's see what creative fakes emerge!",
    "Other players will try matching your phrase.",
    "Looking forward to the impostors!",
    "Fingers crossed for interesting matches!",
    "Others will work their magic soon.",
    "Can't wait to see what happens!",
    "Let's see the creativity unfold!",
  ],
  copySubmitted: [
    "Fake submitted!",
    "Your phrase is in!",
    "Submission received!",
    "Your fake is recorded!",
    "Phrase locked in!",
  ],
  copySubmittedFeedback: [
    "Voters will decide if it matches!",
    "Let's see how voters perceive it.",
    "Your phrase will be reviewed soon.",
    "Hope voters see your connection!",
    "May the voting go your way!",
    "Let's see if voters find it convincing.",
    "Good luck with the vote!",
    "Fingers crossed for your fake!",
  ],
  voteSubmitted: [
    "Vote locked in!",
    "Your pick is in!",
    "Choice recorded!",
    "Decision made!",
    "Let's see if you're right!",
  ],
  voteCorrectHeading: [
    "Correct!",
    "You got it!",
    "Spot on!",
    "Perfect!",
    "Nailed it!",
    "Right on!",
  ],
  voteIncorrectHeading: [
    "Not quite this time",
    "Almost there",
    "Not this round",
    "Better luck next time",
    "Keep trying",
    "So close",
  ],
  voteCorrect: [
    "You identified the original phrase!",
    "You spotted the real deal!",
    "You nailed it!",
    "Your instincts were spot on!",
    "Great eye for originals!",
    "You saw through the fakes!",
    "You're a natural at this!",
  ],
  voteIncorrect: [
    "The original can be tricky!",
    "These can be surprisingly difficult.",
    "The fakes can be quite convincing.",
    "You're learning! Every round helps.",
    "The differences can be subtle.",
    "Sometimes the original is well hidden.",
    "Even experts get fooled sometimes!",
  ],
  bonusClaimed: [
    "Bonus quipped into your bank!",
    "Daily quips collected!",
    "Your wallet just got flipped!",
    "Cha-ching!",
  ],
  prizesClaimed: [
    "Quip-tastic winnings!",
    "You flipped those prizes!",
    "Prizes claimed successfully!",
    "Money in the Quip Bank!",
  ],
};

/**
 * Get a random success message from a category
 */
export const getRandomMessage = (category: keyof typeof successMessages): string => {
  const messages = successMessages[category];
  return messages[Math.floor(Math.random() * messages.length)];
};

/**
 * Loading messages for Quipflip
 */
export const loadingMessages = {
  default: "Shuffling the tiles...",
  starting: "Preparing your quip...",
  submitting: "Flipping your quip...",
  loading: "Loading quips...",
  claiming: "Claiming your quips...",
};
