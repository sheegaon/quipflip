/**
 * Branded success messages for Quipflip
 */

export const successMessages = {
  promptSubmitted: [
    "Phrase submitted!",
    "Your phrase is in!",
    "Submission received!",
    "Thanks for playing!",
    "Your quip is recorded!",
    "Phrase locked in!",
    "Let's see how it goes!",
  ],
  promptSubmittedFeedback: [
    "Let's see what creative copies emerge!",
    "Other players will try matching your phrase.",
    "Looking forward to the copies!",
    "Fingers crossed for interesting matches!",
    "Others will work their magic soon.",
    "Can't wait to see what happens!",
    "Let's hope for clever copies.",
  ],
  copySubmitted: [
    "Copy submitted!",
    "Your phrase is in!",
    "Submission received!",
    "Thanks for playing!",
    "Your copy is recorded!",
    "Phrase locked in!",
    "Let's see how it goes!",
  ],
  copySubmittedFeedback: [
    "Voters will decide if it matches!",
    "Let's see how voters perceive it.",
    "Your phrase will be reviewed soon.",
    "Hope voters see your connection!",
    "May the voting go your way!",
    "Let's see if voters find it convincing.",
    "Good luck with the vote!",
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
    "You saw through the copies!",
    "You're a natural at this!",
  ],
  voteIncorrect: [
    "The original can be tricky!",
    "These can be surprisingly difficult.",
    "The copies can be quite convincing.",
    "You're learning! Every round helps.",
    "The differences can be subtle.",
    "Sometimes the original is well hidden.",
    "Even experts get fooled sometimes!",
  ],
  bonusClaimed: [
    "Bonus quipped into your bank!",
    "Daily quips collected!",
    "Your balance just got flipped!",
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
