import React from 'react';
import './NewUserWelcomeOverlay.css';

interface GuestLogoutWarningProps {
  isVisible: boolean;
  username: string | null;
  guestCredentials: { email: string | null; password: string | null } | null;
  onConfirmLogout: () => void;
  onDismiss: () => void;
}

const GuestLogoutWarning: React.FC<GuestLogoutWarningProps> = ({
  isVisible,
  username,
  guestCredentials,
  onConfirmLogout,
  onDismiss,
}) => {
  if (!isVisible) {
    return null;
  }

  return (
    <div className="guest-welcome-overlay">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="guest-logout-title"
        className="guest-welcome-modal"
      >
        <button
          onClick={onDismiss}
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
          <div className="space-y-2 mb-6">
            <h2 id="guest-logout-title" className="text-2xl font-bold text-quip-navy text-center">
              Save Your Guest Login
            </h2>
          </div>

          <div className="guest-credentials bg-gradient-to-r from-quip-orange to-quip-turquoise text-white md:p-6 px-3 py-6 rounded-tile mb-6 shadow-lg">
            <p className="font-bold md:mb-3 mb-2 text-lg">Guest Credentials</p>
            <p className="text-sm opacity-90 mb-3">
              You&apos;ll need this username/email and password to sign back in after logging out. Keep a copy before you continue.
            </p>
            <div className="bg-white bg-opacity-20 md:p-4 p-2 rounded-lg mb-3 backdrop-blur-sm">
              <p className="my-0 md:my-1 font-mono text-sm">
                <strong>Username:</strong> {username}
              </p>
              <p className="my-0 md:my-1 font-mono text-sm">
                <strong>Email:</strong> {guestCredentials?.email ?? 'Not available'}
              </p>
              {guestCredentials?.password ? (
                <p className="my-0 md:my-1 font-mono text-sm">
                  <strong>Password:</strong> {guestCredentials.password}
                </p>
              ) : (
                <p className="my-0 md:my-1 font-mono text-sm">
                  <strong>Password:</strong> QuipGuest
                </p>
              )}
            </div>
            <div className="text-sm opacity-95">
              <p className="font-semibold mb-2">To log back in later:</p>
              <ol className="list-decimal pl-5 space-y-1">
                <li>Visit the Quipflip login page and choose the &quot;Returning Player&quot; option.</li>
                <li>Enter the username or email and password shown above.</li>
                <li>Continue playing—your progress and coins stay with your guest account.</li>
              </ol>
            </div>
          </div>
        </div>

        <div className="guest-welcome-actions">
          <button
            type="button"
            onClick={onConfirmLogout}
            className="guest-welcome-btn bg-quip-cream text-quip-navy hover:bg-quip-orange/20 hover:shadow-tile-sm transition-all"
          >
            Log Out Now
          </button>
        </div>
      </div>
    </div>
  );
};

export default GuestLogoutWarning;
