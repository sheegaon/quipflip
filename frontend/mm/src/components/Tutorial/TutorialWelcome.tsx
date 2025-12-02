import React, { useState } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { useGame } from '../../contexts/GameContext';
import './TutorialWelcome.css';

interface TutorialWelcomeProps {
  onStart: () => void;
  onSkip: () => void;
}

const TutorialWelcome: React.FC<TutorialWelcomeProps> = ({ onStart, onSkip }) => {
  const {
    state: { tutorialStatus },
  } = useTutorial();
  const { state } = useGame();
  const { player } = state;
  const [isSkipping, setIsSkipping] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  // For guests, always allow showing the welcome screen (they can replay the tutorial)
  // For non-guests, only show if tutorial is inactive (not started or completed)
  if (!player?.is_guest && tutorialStatus !== 'inactive') {
    return null;
  }

  const handleSkip = async () => {
    if (isSkipping || isStarting) return;
    setIsSkipping(true);
    try {
      await onSkip();
    } finally {
      setIsSkipping(false);
    }
  };

  const handleStart = async () => {
    if (isSkipping || isStarting) return;
    setIsStarting(true);
    try {
      await onStart();
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="tutorial-welcome-overlay">
      <div className="tutorial-welcome-modal">
        <button
          onClick={handleSkip}
          disabled={isSkipping || isStarting}
          className="tutorial-welcome-close"
          aria-label="Skip tutorial"
          title="Skip tutorial"
        >
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.1" />
            <path
              d="M8 8L16 16M16 8L8 16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <div className="tutorial-welcome-content">
          <h1 className="tutorial-welcome-title">Welcome to MemeMint!</h1>

          {player?.username && (
            <p className="tutorial-welcome-username">
              You've been assigned the username <strong>{player?.username}</strong> — this is how other players in the game will see you.
            </p>
          )}

          <p className="tutorial-welcome-description">
            MemeMint is an asynchronous meme-caption battler where you:
          </p>

          <ul className="tutorial-welcome-features">
            <li>
              <strong>Vote:</strong> Pay an entry fee to choose the best caption out of five for each meme image
            </li>
            <li>
              <strong>Caption:</strong> Add your own original caption or riff on someone else's after you vote
            </li>
            <li>
              <strong>Earn MemeCoins:</strong> Winning captions get paid, and voters can earn bonuses
            </li>
            <li>
              <strong>Replay:</strong> Images and captions stay in circulation so you can refine and compete again
            </li>
          </ul>

          <p className="tutorial-welcome-cta">
            Would you like a quick tutorial to learn how to play?
          </p>
        </div>

        <div className="tutorial-welcome-actions">
          <button
            onClick={handleStart}
            disabled={isSkipping || isStarting}
            className="tutorial-welcome-btn tutorial-welcome-btn-primary"
          >
            {isStarting ? 'Starting...' : 'Start Tutorial'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TutorialWelcome;
