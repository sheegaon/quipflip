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
          <strong>Get a prompt:</strong> You'll receive a question like "Name something people forget at home" that needs short phrase answers.
        </li>
        <li>
          <strong>Submit answers:</strong> Pay the entry fee (100 coins) and start guessing with 2-5 word phrases that match what others have said.
        </li>
        <li>
          <strong>Match the crowd:</strong> Your goal is to think like previous players - the more popular ideas you match, the more you win.
        </li>
        <li>
          <strong>Avoid strikes:</strong> If your answer doesn't match anyone else's, you get a strike. Three strikes and the round ends.
        </li>
        <li>
          <strong>Score big:</strong> Cover more of the crowd's semantic space to earn up to 300 coins per round, with bonuses going to your vault.
        </li>
      </ol>

      <div className="guest-welcome-example">
        <strong>Example:</strong> For "Things people forget at home," you might guess "keys," "wallet," or "phone" - common answers that match what others have submitted before.
      </div>

      <hr className="guest-welcome-divider" />

      <div className="guest-welcome-login-prompt">
        <LeaderboardIcon className="h-14 w-14" />
        <p className="text-center">
          You&apos;ll be able to save your progress after your first finished game.
        </p>
      </div>
    </NewUserWelcomeOverlayShell>
  );
};

export default NewUserWelcomeOverlay;
