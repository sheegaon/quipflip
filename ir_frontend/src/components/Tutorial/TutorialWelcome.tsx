import React, { useState } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { useIRGame } from '../../contexts/IRGameContext';
import './TutorialWelcome.css';

interface TutorialWelcomeProps {
  onStart: () => void;
  onSkip: () => void;
}

const TutorialWelcome: React.FC<TutorialWelcomeProps> = ({ onStart, onSkip }) => {
  const { tutorialStatus } = useTutorial();
  const { player } = useIRGame();
  const [isSkipping, setIsSkipping] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

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
          <h1 className="tutorial-welcome-title">Welcome to Initial Reaction!</h1>

          {player?.username && (
            <p className="tutorial-welcome-username">
              You're playing as <strong>{player?.username}</strong>. This name appears on your backronyms and leaderboards.
            </p>
          )}

          <p className="tutorial-welcome-description">
            In each battle you'll turn a 3–5 letter word into a backronym, then vote on the best entry.
          </p>

          <ul className="tutorial-welcome-features">
            <li>
              <strong>Create Backronyms:</strong> Spend 100 InitCoins to enter and craft one word per letter.
            </li>
            <li>
              <strong>Vote Smart:</strong> Participants vote free; observers pay 10 IC but win 20 IC when they match the crowd.
            </li>
            <li>
              <strong>Watch the Clock:</strong> Rapid mode fills with AI after 2 minutes; Standard gives humans 30 minutes.
            </li>
            <li>
              <strong>Grow Your Vault:</strong> 30% of net winnings auto-saves, so consistency matters.
            </li>
          </ul>

          <p className="tutorial-welcome-cta">
            Want a quick walkthrough before you battle?
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
