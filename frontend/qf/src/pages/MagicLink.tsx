import React from 'react';
import CredentialAccountPanel from '../components/CredentialAccountPanel';

const MagicLink: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-ccl-orange to-ccl-orange-deep bg-pattern">
      <div className="tile-card max-w-lg w-full p-8">
        <CredentialAccountPanel
          mode="signin"
          title="Sign in"
          description="Use the email and password you saved with your account."
          ctaLabel="Sign in"
          navigateOnSuccess
        />
      </div>
    </div>
  );
};

export default MagicLink;
