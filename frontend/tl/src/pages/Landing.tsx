import React from 'react';
import GuestFirstLanding from '@crowdcraft/components/GuestFirstLanding.tsx';

export const Landing: React.FC = () => {
  return (
    <GuestFirstLanding
      logoSrc="/landing_logo.png"
      logoAlt="ThinkLink"
      title="Solve patterns. Match the crowd. Win ThinkCoins."
      subtitle="New visitors start as guests automatically. Returning players can restore their account with email."
      signInPath="/auth/magic-link"
      className="bg-gradient-to-br from-ccl-teal to-ccl-orange"
    />
  );
};

export default Landing;
