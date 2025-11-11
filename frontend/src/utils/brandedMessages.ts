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
    "Your phrase is now in the mix. Let's see what creative copies emerge!",
    "Thanks for contributing! Other players will try to match your phrase soon.",
    "Your submission helps keep the game moving. Looking forward to the copies!",
    "Your phrase is ready for the challenge. Fingers crossed for some interesting matches!",
    "All set! Other players will work their magic with your phrase.",
    "Your creativity fuels the game. Can't wait to see what happens next!",
    "Submission complete! Let's hope for some clever copies.",
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
    "Your phrase is submitted! Voters will decide if it matches the original.",
    "Thanks for your entry! Let's see how voters perceive your phrase.",
    "All done! Your phrase will be reviewed alongside the others soon.",
    "Submission complete! Hoping the voters see the connection you made.",
    "Your copy is in the mix. May the voting go your way!",
    "Thanks for contributing! Let's see if voters find your phrase convincing.",
    "Your phrase is ready for judgment. Good luck with the vote!",
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
