import React from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import './TutorialWelcome.css';

interface TutorialWelcomeProps {
  onStart: () => void;
  onSkip: () => void;
}

const TutorialWelcome: React.FC<TutorialWelcomeProps> = ({ onStart, onSkip }) => {
  const { tutorialStatus } = useTutorial();

  // Only show if tutorial hasn't been started or completed
  if (!tutorialStatus || tutorialStatus.tutorial_progress !== 'not_started') {
    return null;
  }

  return (
    <div className="tutorial-welcome-overlay">
      <div className="tutorial-welcome-modal">
        <div className="tutorial-welcome-content">
          <h1 className="tutorial-welcome-title">Welcome to Quipflip!</h1>

          <p className="tutorial-welcome-description">
            Quipflip is a creative word game where you can:
          </p>

          <ul className="tutorial-welcome-features">
            <li>
              <strong>Create Quips:</strong> Write fun fill-in-the-blank challenges
            </li>
            <li>
              <strong>Copy Phrases:</strong> Try to blend in with the original answers
            </li>
            <li>
              <strong>Vote:</strong> Identify the original phrase from clever copies
            </li>
            <li>
              <strong>Earn Coins:</strong> The more creative you are, the more you earn!
            </li>
          </ul>

          <p className="tutorial-welcome-cta">
            Would you like a quick tutorial to learn how to play?
          </p>
        </div>

        <div className="tutorial-welcome-actions">
          <button
            onClick={onSkip}
            className="tutorial-welcome-btn tutorial-welcome-btn-secondary"
          >
            Skip for Now
          </button>
          <button
            onClick={onStart}
            className="tutorial-welcome-btn tutorial-welcome-btn-primary"
          >
            Start Tutorial
          </button>
        </div>
      </div>
    </div>
  );
};

export default TutorialWelcome;
