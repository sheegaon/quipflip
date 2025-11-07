import React, { useState, useEffect } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { useGame } from '../../contexts/GameContext';
import './TutorialWelcome.css';

interface TutorialWelcomeProps {
  onStart: () => void;
  onSkip: () => void;
}

interface GuestCredentials {
  email: string;
  password: string;
  timestamp: number;
}

const TutorialWelcome: React.FC<TutorialWelcomeProps> = ({ onStart, onSkip }) => {
  const { tutorialStatus } = useTutorial();
  const { state } = useGame();
  const { player } = state;
  const [isSkipping, setIsSkipping] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [guestCredentials, setGuestCredentials] = useState<GuestCredentials | null>(null);
  const [showGuestCredentialsScreen, setShowGuestCredentialsScreen] = useState(false);

  // Check for guest credentials in localStorage
  useEffect(() => {
    if (!player?.is_guest) {
      setGuestCredentials(null);
      setShowGuestCredentialsScreen(false);
      return;
    }

    const stored = localStorage.getItem('quipflip_guest_credentials');
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as GuestCredentials;
        // Only use if less than 5 minutes old
        if (Date.now() - parsed.timestamp < 5 * 60 * 1000) {
          setGuestCredentials(parsed);
          setShowGuestCredentialsScreen(true);
          return;
        } else {
          // Clean up old credentials
          localStorage.removeItem('quipflip_guest_credentials');
        }
      } catch (e) {
        console.error('Failed to parse guest credentials', e);
      }
    }

  }, [player?.is_guest]);

  // Clean up credentials when tutorial starts or is skipped
  const cleanupCredentials = () => {
    localStorage.removeItem('quipflip_guest_credentials');
    setGuestCredentials(null);
  };

  const handleDismissGuestCredentials = () => {
    setShowGuestCredentialsScreen(false);
  };

  // Only show if tutorial hasn't been started or completed
  if (tutorialStatus !== 'inactive') {
    return null;
  }

  const handleSkip = async () => {
    if (isSkipping || isStarting) return;
    setIsSkipping(true);
    try {
      cleanupCredentials();
      await onSkip();
    } finally {
      setIsSkipping(false);
    }
  };

  const handleStart = async () => {
    if (isSkipping || isStarting) return;
    setIsStarting(true);
    try {
      cleanupCredentials();
      await onStart();
    } finally {
      setIsStarting(false);
    }
  };

  if (
    showGuestCredentialsScreen &&
    guestCredentials &&
    player?.is_guest
  ) {
    return (
      <div className="tutorial-welcome-overlay">
        <div className="tutorial-welcome-modal">
          <div className="tutorial-welcome-content">
            <h1 className="tutorial-welcome-title">Your Guest Account</h1>
            <div className="tutorial-guest-credentials bg-gradient-to-r from-quip-orange to-quip-turquoise text-white p-6 rounded-tile mb-6 shadow-lg">
              <p className="font-bold mb-3 text-lg">Your Guest Account Credentials</p>
              <div className="bg-white bg-opacity-20 p-4 rounded-lg mb-3 backdrop-blur-sm">
                <p className="my-1 font-mono text-sm">
                  <strong>Email:</strong> {guestCredentials.email}
                </p>
                <p className="my-1 font-mono text-sm">
                  <strong>Password:</strong> {guestCredentials.password}
                </p>
              </div>
              <p className="text-sm opacity-95">
                Save these credentials to log in later! You can upgrade to a full account anytime in Settings.
              </p>
            </div>
            <p className="tutorial-welcome-description">
              Keep these safe—once you dismiss this screen, the tutorial will begin.
            </p>
          </div>
          <div className="tutorial-welcome-actions">
            <button
              onClick={handleDismissGuestCredentials}
              className="tutorial-welcome-btn tutorial-welcome-btn-primary"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tutorial-welcome-overlay">
      <div className="tutorial-welcome-modal">
        <div className="tutorial-welcome-content">
          <h1 className="tutorial-welcome-title">Welcome to Quipflip!</h1>

          {player?.username && (
            <p className="tutorial-welcome-username">
              You've been assigned the username <strong>{player?.username}</strong> — this is how other players in the game will see you.
            </p>
          )}

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
              <strong>Earn Coins:</strong> The more clever your quips, the more you earn!
            </li>
          </ul>

          <p className="tutorial-welcome-cta">
            Would you like a quick tutorial to learn how to play?
          </p>
        </div>

        <div className="tutorial-welcome-actions">
          <button
            onClick={handleSkip}
            disabled={isSkipping || isStarting}
            className="tutorial-welcome-btn tutorial-welcome-btn-secondary"
          >
            {isSkipping ? 'Skipping...' : 'Skip for Now'}
          </button>
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
