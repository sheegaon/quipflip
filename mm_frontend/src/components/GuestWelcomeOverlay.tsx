import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { GUEST_CREDENTIALS_KEY, GUEST_CREDENTIALS_SHOWN_KEY } from '../utils/storageKeys';
import { LeaderboardIcon } from './icons/NavigationIcons';
import './GuestWelcomeOverlay.css';

const GuestWelcomeOverlay: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { logout } = actions;
  const navigate = useNavigate();

  const [isVisible, setIsVisible] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    // Only show for guest users
    if (!player?.is_guest) {
      setIsVisible(false);
      return;
    }

    // Check if we've already shown the overlay for this session
    const hasShown = sessionStorage.getItem(GUEST_CREDENTIALS_SHOWN_KEY);
    if (hasShown) {
      return;
    }

    // Show the welcome overlay for all guest users who haven't seen it this session
    setIsVisible(true);
  }, [player?.is_guest]);

  const handleDismiss = () => {
    // Mark as shown for this session
    sessionStorage.setItem(GUEST_CREDENTIALS_SHOWN_KEY, 'true');

    // Don't clear credentials - allow guest to remain logged in
    setIsVisible(false);
  };

  const handleLoginClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      setIsLoggingOut(true);

      // Mark as shown to prevent re-display
      sessionStorage.setItem(GUEST_CREDENTIALS_SHOWN_KEY, 'true');

      // Clean up credentials
      localStorage.removeItem(GUEST_CREDENTIALS_KEY);

      // Logout and navigate to landing
      await logout();
      navigate('/');
    } catch (error) {
      console.error('Failed to logout:', error);
      setIsLoggingOut(false);
    }
  };

  if (!isVisible || !player?.is_guest) {
    return null;
  }

  return (
    <div className="guest-welcome-overlay">
      <div className="guest-welcome-modal">
        <button
          onClick={handleDismiss}
          disabled={isLoggingOut}
          className="guest-welcome-close"
          aria-label="Close"
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

        <div className="guest-welcome-content">
          <div className="flex justify-center mb-4">
            <img src="/mememint_logo.png" alt="MemeMint Logo" className="h-16" />
          </div>

          <h2 className="guest-welcome-title">How To Play</h2>

          <ol className="guest-welcome-list">
            <li>
              <strong>See an image + captions:</strong> We show you one image with five captions to
              read.
            </li>
            <li>
              <strong>Vote:</strong> Pay the entry fee, view the image with five captions, and pick
              your favorite.
            </li>
            <li>
              <strong>Win + bonuses:</strong> The authors of the winning caption (riff + parent, or
              original) get paid in MemeCoins. The system may also pay voter bonuses.
            </li>
            <li>
              <strong>Add your own:</strong> After voting, submit a new caption (original or riff)
              for the image.
            </li>
            <li>
              <strong>Replayable:</strong> Images and captions cycle indefinitely; weak captions are
              retired over time.
            </li>
          </ol>

          <div className="guest-welcome-example">
            <strong>Example:</strong> You'll see a meme image along with five captions. Choose your
            favorite, then add your own caption for that image (either an original or a riff).
          </div>

          <hr className="guest-welcome-divider" />

          <div className="guest-welcome-login-prompt">
            <LeaderboardIcon className="h-14 w-14" />
            <p>
              <a
                href="#"
                onClick={handleLoginClick}
                className="guest-welcome-login-link"
              >
                {isLoggingOut ? 'Logging out...' : 'Log in or create a free account'}
              </a>{' '}
              to link your stats.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GuestWelcomeOverlay;
