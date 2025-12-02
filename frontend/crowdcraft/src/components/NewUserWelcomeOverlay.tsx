import React from 'react';
import './NewUserWelcomeOverlay.css';

interface NewUserWelcomeOverlayProps {
  isVisible: boolean;
  logoSrc: string;
  logoAlt: string;
  onDismiss: () => void;
  children: React.ReactNode;
  isCloseDisabled?: boolean;
}

const NewUserWelcomeOverlay: React.FC<NewUserWelcomeOverlayProps> = ({
  isVisible,
  logoSrc,
  logoAlt,
  onDismiss,
  children,
  isCloseDisabled = false,
}) => {
  if (!isVisible) {
    return null;
  }

  return (
    <div className="guest-welcome-overlay">
      <div className="guest-welcome-modal">
        <button
          onClick={onDismiss}
          disabled={isCloseDisabled}
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
            <img src={logoSrc} alt={logoAlt} className="h-16" />
          </div>

          {children}
        </div>
      </div>
    </div>
  );
};

export default NewUserWelcomeOverlay;
