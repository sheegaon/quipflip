import React from 'react';
import type { PhrasesetDetails as PhrasesetDetailsType, PhrasesetSummary } from '@crowdcraft/api/types.ts';

// Placeholder component - will be replaced with MM caption details view
export const PhrasesetDetails: React.FC<{
  phraseset: PhrasesetDetailsType | null;
  summary: PhrasesetSummary;
}> = () => {
  return (
    <div className="p-6 text-center text-ccl-teal">
      Caption details coming soon
    </div>
  );
};

export default PhrasesetDetails;
