import React from 'react';

// Placeholder component - will be replaced with MM caption tracking list
export const PhrasesetList: React.FC<{
  phrasesets: any[];
  selectedId: string | null;
  onSelect: (item: any) => void;
}> = () => {
  return (
    <div className="p-6 text-center text-quip-teal">
      Caption tracking coming soon
    </div>
  );
};

export default PhrasesetList;
