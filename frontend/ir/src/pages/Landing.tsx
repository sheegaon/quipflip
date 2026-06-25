import React from 'react';
import GuestFirstLanding from '@crowdcraft/components/GuestFirstLanding.tsx';
import { useIRGame } from '../contexts/IRGameContext';

export const Landing: React.FC = () => {
  const { loading, loginAsGuest } = useIRGame();

  return (
    <GuestFirstLanding
      logoSrc="/landing_logo.png"
      logoAlt="Initial Reaction"
      title="Create clever backronyms and vote on your favorites."
      subtitle="New visitors start as guests automatically. Returning players can restore their account with email."
      primaryActionLabel="Continue as guest"
      primaryActionLoadingLabel="Opening guest account..."
      onPrimaryAction={() => loginAsGuest()}
      primaryActionDisabled={loading}
      signInPath="/auth/magic-link"
      className="bg-gradient-to-br from-ir-orange to-ir-orange-deep"
    />
  );
};

export default Landing;
