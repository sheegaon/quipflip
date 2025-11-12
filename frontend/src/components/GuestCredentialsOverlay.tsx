import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { GUEST_CREDENTIALS_KEY, GUEST_CREDENTIALS_SHOWN_KEY } from '../utils/storageKeys';
import './GuestCredentialsOverlay.css';

interface GuestCredentials {
  email: string;
  password: string;
  timestamp: number;
}

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
    const hasShown = sessionStorage.getItem(GUEST_CREDENTIALS_SHOWN_KEY);
    if (hasShown) {
      return;
    }

    // Try to load credentials from localStorage
    const stored = localStorage.getItem(GUEST_CREDENTIALS_KEY);
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
          localStorage.removeItem(GUEST_CREDENTIALS_KEY);
        }
      } catch (e) {
        console.error('Failed to parse guest credentials', e);
        localStorage.removeItem(GUEST_CREDENTIALS_KEY);
      }
    }
  }, [player?.is_guest]);

  const handleDismiss = () => {
    // Mark as shown for this session
    sessionStorage.setItem(GUEST_CREDENTIALS_SHOWN_KEY, 'true');

    // Clean up credentials from localStorage
    localStorage.removeItem(GUEST_CREDENTIALS_KEY);

    setIsVisible(false);
    setGuestCredentials(null);
  };

  const handleExistingUser = async () => {
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

  if (!isVisible || !guestCredentials || !player?.is_guest) {
    return null;
  }

  return (
    <div className="guest-welcome-overlay">
      <div className="guest-welcome-modal">
        <div className="guest-welcome-content">
          <div className="flex justify-center mb-2 md:mb-6">
            <img src="/quipflip_logo.png" alt="Quipflip Logo" className="h-16" />
          </div>
          <h2 className="guest-welcome-description md:mb-4 mb-1">
            Welcome to Quipflip!
          </h2>
          <div className="guest-credentials bg-gradient-to-r from-quip-orange to-quip-turquoise text-white md:p-6 px-3 py-6 rounded-tile mb-6 shadow-lg">
            <p className="font-bold md:mb-3 mb-2 text-lg">Guest Account Credentials</p>
            <div className="bg-white bg-opacity-20 md:p-4 p-2 rounded-lg mb-3 backdrop-blur-sm">
              <p className="my-0 md:my-1 font-mono text-sm">
                <strong>Username:</strong> {player.username}
              </p>
              <p className="my-0 md:my-1 font-mono text-sm">
                <strong>Email:</strong> {guestCredentials.email}
              </p>
              <p className="my-0 md:my-1 font-mono text-sm">
                <strong>Password:</strong> {guestCredentials.password}
              </p>
            </div>
            <p className="text-sm opacity-95">
              Save these credentials to log in later! You can upgrade to a full account anytime in Settings.
            </p>
          </div>
        </div>
        <div className="guest-welcome-actions">
          <button
            onClick={handleExistingUser}
            disabled={isLoggingOut}
            className="guest-welcome-btn bg-quip-cream text-quip-navy hover:bg-quip-orange/20 hover:shadow-tile-sm transition-all"
          >
            {isLoggingOut ? 'Logging out...' : 'Existing User'}
          </button>
          <button
            onClick={handleDismiss}
            disabled={isLoggingOut}
            className="guest-welcome-btn bg-quip-navy text-white hover:bg-quip-navy/90 hover:shadow-tile-sm transition-all"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};

export default GuestCredentialsOverlay;
