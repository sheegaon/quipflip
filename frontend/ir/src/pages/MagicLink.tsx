import React from 'react';
import MagicLinkPanel from '@crowdcraft/components/MagicLinkPanel.tsx';
import { GUEST_CREDENTIALS_KEY } from '../utils/storageKeys';

const MagicLink: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-ir-orange to-ir-orange-deep bg-pattern">
      <div className="tile-card max-w-lg w-full p-8">
        <MagicLinkPanel
          mode="signin"
          title="Save your account"
          description="Enter your email and we’ll send a link to continue on this device or another one."
          ctaLabel="Send sign-in link"
          placeholder="tal@example.com"
          autoNavigateOnSuccess
          guestCredentialsStorageKey={GUEST_CREDENTIALS_KEY}
        />
      </div>
    </div>
  );
};

export default MagicLink;
