import React, { useEffect, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { LeaderboardIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import NewUserWelcomeOverlayShell from '@crowdcraft/components/NewUserWelcomeOverlay.tsx';

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
      logoAlt="MemeMint Logo"
      onDismiss={handleDismiss}
    >
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
          <strong>Add your own:</strong> After voting, submit a new caption (original or riff) for
          the image.
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
        <p className="text-center">
          You&apos;ll be able to save your stats after your first finished game.
        </p>
      </div>
    </NewUserWelcomeOverlayShell>
  );
};

export default NewUserWelcomeOverlay;
