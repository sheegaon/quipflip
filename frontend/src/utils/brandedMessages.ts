/**
 * Branded success messages for Quipflip
 */

export const successMessages = {
  promptSubmitted: [
    "Nice quip!",
    "You flipped it!",
    "Quip-tastic submission!",
    "That's a keeper!",
    "Brilliant quip!",
  ],
  copySubmitted: [
    "Perfect flip!",
    "You nailed the copy!",
    "Matched like a pro!",
    "Quip copied successfully!",
    "Great minds flip alike!",
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
    "Excellent work! You successfully identified the original phrase!",
    "Brilliant! You spotted the real deal!",
    "Outstanding! You nailed it!",
    "Well done! Your instincts were spot on!",
    "Fantastic! You've got a great eye for originals!",
    "Impressive! You saw right through the copies!",
    "Superb! You're a natural at this!",
  ],
  voteIncorrect: [
    "No worries! The original can be tricky to spot. Keep practicing and you'll master it!",
    "Don't be discouraged! These can be surprisingly difficult. You'll get the next one!",
    "Good try! The copies can be quite convincing. Keep at it!",
    "Not this time, but you're learning! Every round makes you sharper!",
    "Close one! The differences can be subtle. You're improving with each vote!",
    "Nice effort! Sometimes the original is well hidden. Keep going!",
    "Keep your head up! Even the experts get fooled sometimes!",
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
