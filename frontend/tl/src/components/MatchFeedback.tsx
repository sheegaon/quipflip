import React from 'react';

interface Guess {
  text: string;
  wasMatch: boolean;
  causedStrike: boolean;
  timestamp: number;
}

interface MatchFeedbackProps {
  guesses: Guess[];
  title?: string;
  maxVisible?: number;
  showLabel?: boolean;
}

export const MatchFeedback: React.FC<MatchFeedbackProps> = ({
  guesses,
  title = 'Recent Guesses',
  maxVisible = 5,
  showLabel = true,
}) => {
  if (guesses.length === 0) {
    return null;
  }

  // Show most recent guesses first, limited by maxVisible
  const displayedGuesses = [...guesses].reverse().slice(0, maxVisible);

  const getGuessStyle = (guess: Guess) => {
    if (guess.wasMatch) {
      return {
        container: 'bg-green-50 border-l-4 border-green-500',
        text: 'text-green-900',
        icon: '✓',
      };
    } else if (guess.causedStrike) {
      return {
        container: 'bg-red-50 border-l-4 border-red-500',
        text: 'text-red-900',
        icon: '✗',
      };
    } else {
      return {
        container: 'bg-gray-50 border-l-4 border-gray-400',
        text: 'text-gray-700',
        icon: '○',
      };
    }
  };

  return (
    <div className="tile-card p-6">
      {showLabel && (
        <h3 className="font-bold text-ccl-navy mb-4">{title}</h3>
      )}

      <div className="space-y-2 max-h-48 overflow-y-auto">
        {displayedGuesses.map((guess, index) => {
          const style = getGuessStyle(guess);
          return (
            <div
              key={guess.timestamp}
              className={`
                p-3 rounded-lg text-sm font-mono
                ${style.container} ${style.text}
                animate-fade-in transition-all duration-200
              `}
            >
              <span className="mr-2 font-bold">{style.icon}</span>
              {guess.text}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MatchFeedback;
