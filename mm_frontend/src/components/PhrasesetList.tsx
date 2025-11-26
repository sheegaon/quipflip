import React from 'react';
import type { PhrasesetSummary } from '../api/types';

// Placeholder component - will be replaced with MM caption tracking list
export const PhrasesetList: React.FC<{
  phrasesets: PhrasesetSummary[];
  selectedId: string | null;
  onSelect: (item: PhrasesetSummary) => void;
}> = () => {
  return (
    <div className="p-6 text-center text-quip-teal">
      Caption tracking coming soon
    </div>
  );
};

export default PhrasesetList;
