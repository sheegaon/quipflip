import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import './Tutorial/TutorialWelcome.css';

interface GuestCredentials {
  email: string;
  password: string;
  timestamp: number;
}

const CREDENTIALS_STORAGE_KEY = 'quipflip_guest_credentials';
const CREDENTIALS_SHOWN_KEY = 'quipflip_guest_credentials_shown';

const GuestCredentialsOverlay: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { logout } = actions;
  const navigate = useNavigate();

  const [guestCredentials, setGuestCredentials] = useState<GuestCredentials | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    // Only show for guest users
    if (!player?.is_guest) {
      setIsVisible(false);
      setGuestCredentials(null);
      return;
    }

    // Check if we've already shown credentials for this session
    const hasShown = sessionStorage.getItem(CREDENTIALS_SHOWN_KEY);
    if (hasShown) {
      return;
    }

    // Try to load credentials from localStorage
    const stored = localStorage.getItem(CREDENTIALS_STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as GuestCredentials;
        // Only use if less than 5 minutes old
        if (Date.now() - parsed.timestamp < 5 * 60 * 1000) {
          setGuestCredentials(parsed);
          setIsVisible(true);
          return;
        } else {
          // Clean up old credentials
          localStorage.removeItem(CREDENTIALS_STORAGE_KEY);
        }
      } catch (e) {
        console.error('Failed to parse guest credentials', e);
        localStorage.removeItem(CREDENTIALS_STORAGE_KEY);
      }
    }
  }, [player?.is_guest]);

  const handleDismiss = () => {
    // Mark as shown for this session
    sessionStorage.setItem(CREDENTIALS_SHOWN_KEY, 'true');

    // Clean up credentials from localStorage
    localStorage.removeItem(CREDENTIALS_STORAGE_KEY);

    setIsVisible(false);
    setGuestCredentials(null);
  };

  const handleExistingUser = async () => {
    try {
      setIsLoggingOut(true);

      // Mark as shown to prevent re-display
      sessionStorage.setItem(CREDENTIALS_SHOWN_KEY, 'true');

      // Clean up credentials
      localStorage.removeItem(CREDENTIALS_STORAGE_KEY);

      // Logout and navigate to landing
      await logout();
      navigate('/');
    } catch (error) {
      console.error('Failed to logout:', error);
      setIsLoggingOut(false);
    }
  };

  if (!isVisible || !guestCredentials || !player?.is_guest) {
    return null;
  }

  return (
    <div className="tutorial-welcome-overlay">
      <div className="tutorial-welcome-modal">
        <div className="tutorial-welcome-content">
          <h1 className="tutorial-welcome-title">Your Guest Account</h1>
          <p className="tutorial-welcome-description">
            If you already have a Quipflip account, log out and log back in using your credentials.
          </p>
          <div className="tutorial-guest-credentials bg-gradient-to-r from-quip-orange to-quip-turquoise text-white p-6 rounded-tile mb-6 shadow-lg">
            <p className="font-bold mb-3 text-lg">Your Guest Account Credentials</p>
            <div className="bg-white bg-opacity-20 p-4 rounded-lg mb-3 backdrop-blur-sm">
              <p className="my-1 font-mono text-sm">
                <strong>Username:</strong> {player.username}
              </p>
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
            You can view these again from the Settings or Statistics pages.
          </p>
        </div>
        <div className="tutorial-welcome-actions">
          <button
            onClick={handleExistingUser}
            disabled={isLoggingOut}
            className="tutorial-welcome-btn tutorial-welcome-btn-secondary"
          >
            {isLoggingOut ? 'Logging out...' : 'Existing User'}
          </button>
          <button
            onClick={handleDismiss}
            disabled={isLoggingOut}
            className="tutorial-welcome-btn tutorial-welcome-btn-primary"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};

export default GuestCredentialsOverlay;
