import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { GUEST_CREDENTIALS_KEY } from '@crowdcraft/utils/storageKeys.ts';
import { LeaderboardIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import '@crowdcraft/components/NewUserWelcomeOverlay.css';
import QFWelcomeInstructions from './QFWelcomeInstructions';

const NewUserWelcomeOverlay: React.FC = () => {
  const { state, actions } = useGame();
  const { player, showNewUserWelcome } = state;
  const { logout, dismissNewUserWelcome } = actions;
  const navigate = useNavigate();

  const [isVisible, setIsVisible] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (showNewUserWelcome && player) {
      setIsVisible(true);
    } else {
      setIsVisible(false);
    }
  }, [showNewUserWelcome, player]);

  const handleDismiss = () => {
    setIsVisible(false);
    dismissNewUserWelcome();
  };

  const handleLoginClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (!player?.is_guest) return;

    try {
      setIsLoggingOut(true);
      localStorage.removeItem(GUEST_CREDENTIALS_KEY);

      await logout();
      dismissNewUserWelcome();
      navigate('/');
    } catch (error) {
      console.error('Failed to logout:', error);
      setIsLoggingOut(false);
    }
  };

  if (!isVisible || !player) {
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
            <img src="/quipflip_logo.png" alt="Quipflip Logo" className="h-16" />
          </div>

          <QFWelcomeInstructions />

          <hr className="guest-welcome-divider" />

          {player.is_guest ? (
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
          ) : (
            <div className="guest-welcome-login-prompt">
              <LeaderboardIcon className="h-14 w-14" />
              <p className="text-center">
                You&apos;re all set! Head to your dashboard to start playing and track your stats.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NewUserWelcomeOverlay;
