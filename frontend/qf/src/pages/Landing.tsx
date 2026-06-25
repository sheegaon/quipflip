import React from 'react';
import GuestFirstLanding from '@crowdcraft/components/GuestFirstLanding.tsx';
import { useGame } from '../contexts/GameContext';

export const Landing: React.FC = () => {
  const { state, actions } = useGame();

  return (
    <GuestFirstLanding
      logoSrc="/landing_logo.png"
      logoAlt="Quipflip"
      title="Write a quip. Fake a quip. Guess the original."
      subtitle="New visitors start as guests automatically. Returning players can sign in with email and password."
      primaryActionLabel="Continue as guest"
      primaryActionLoadingLabel="Opening guest account..."
      onPrimaryAction={actions.continueAsGuest}
      primaryActionDisabled={state.loading}
      signInPath="/auth/magic-link"
      signInHint="Guest progress lives on this device until you save it. Returning players can sign in with their saved account."
      className="bg-gradient-to-br from-ccl-orange to-ccl-orange-deep"
    />
  );
};

export default Landing;
