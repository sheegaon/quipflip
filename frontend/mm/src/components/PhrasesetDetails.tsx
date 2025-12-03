import React from 'react';
import type { MMPhrasesetDetails as PhrasesetDetailsType, MMPhrasesetSummary } from '@crowdcraft/api/types.ts';

// Placeholder component - will be replaced with MM caption details view
export const MMPhrasesetDetails: React.FC<{
  phraseset: PhrasesetDetailsType | null;
  summary: MMPhrasesetSummary;
}> = () => {
  return (
    <div className="p-6 text-center text-ccl-teal">
      Caption details coming soon
    </div>
  );
};

export default MMPhrasesetDetails;
