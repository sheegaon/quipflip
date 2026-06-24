import React, { useEffect, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { LeaderboardIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import NewUserWelcomeOverlayShell from '@crowdcraft/components/NewUserWelcomeOverlay.tsx';
import QFWelcomeInstructions from './QFWelcomeInstructions';

const NewUserWelcomeOverlay: React.FC = () => {
  const { state, actions } = useGame();
  const { player, showNewUserWelcome } = state;
  const { dismissNewUserWelcome } = actions;

  const [isVisible, setIsVisible] = useState(false);

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

  if (!isVisible || !player) {
    return null;
  }

  return (
    <NewUserWelcomeOverlayShell
      isVisible={isVisible}
      logoSrc="/landing_logo.png"
      logoAlt="Quipflip Logo"
      onDismiss={handleDismiss}
    >
      <QFWelcomeInstructions />

      <hr className="guest-welcome-divider" />

      <div className="guest-welcome-login-prompt">
        <LeaderboardIcon className="h-14 w-14" />
        <p className="text-center">
          You&apos;ll be able to save your stats after your first finished game.
        </p>
      </div>
    </NewUserWelcomeOverlayShell>
  );
};

export default NewUserWelcomeOverlay;
