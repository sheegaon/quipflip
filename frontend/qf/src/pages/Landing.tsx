import React from 'react';
import GuestFirstLanding from '@crowdcraft/components/GuestFirstLanding.tsx';

export const Landing: React.FC = () => {
  return (
    <GuestFirstLanding
      logoSrc="/landing_logo.png"
      logoAlt="Quipflip"
      title="Write a quip. Fake a quip. Guess the original."
      subtitle="New visitors start as guests automatically. Returning players can restore their account with email."
      signInPath="/auth/magic-link"
      className="bg-gradient-to-br from-ccl-orange to-ccl-orange-deep"
    />
  );
};

export default Landing;
