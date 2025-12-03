import React from 'react';
import type { MMPhrasesetSummary } from '@crowdcraft/api/types.ts';

// Placeholder component - will be replaced with MM caption tracking list
export const PhrasesetList: React.FC<{
  phrasesets: MMPhrasesetSummary[];
  selectedId: string | null;
  onSelect: (item: MMPhrasesetSummary) => void;
}> = () => {
  return (
    <div className="p-6 text-center text-ccl-teal">
      Caption tracking coming soon
    </div>
  );
};

export default PhrasesetList;
