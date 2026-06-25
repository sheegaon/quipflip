import React from 'react';
import GuestFirstLanding from '@crowdcraft/components/GuestFirstLanding.tsx';
import { useGame } from '../contexts/GameContext';

export const Landing: React.FC = () => {
  const { state, actions } = useGame();

  return (
    <GuestFirstLanding
      logoSrc="/landing_logo.png"
      logoAlt="MemeMint"
      title="Guess what the crowd said and earn coins!"
      subtitle="New visitors start as guests automatically. Returning players can restore their account with email."
      primaryActionLabel="Continue as guest"
      primaryActionLoadingLabel="Opening guest account..."
      onPrimaryAction={actions.continueAsGuest}
      primaryActionDisabled={state.loading}
      signInPath="/auth/magic-link"
      className="bg-gradient-to-br from-ccl-orange to-ccl-orange-deep"
    />
  );
};

export default Landing;
