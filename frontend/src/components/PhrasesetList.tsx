import React from 'react';
import type { PhrasesetSummary } from '../api/types';
import { StatusBadge } from './StatusBadge';
import { getUniqueIdForSummary } from '../utils/phrasesetHelpers';

interface PhrasesetListProps {
  phrasesets: PhrasesetSummary[];
  selectedId?: string | null;
  onSelect: (phraseset: PhrasesetSummary) => void;
  isLoading?: boolean;
}

const formatLabel = (phrase: string) => {
  if (!phrase) return '—';
  return phrase.length > 60 ? `${phrase.slice(0, 57)}…` : phrase;
};

export const PhrasesetList: React.FC<PhrasesetListProps> = ({
  phrasesets,
  selectedId,
  onSelect,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 text-center text-sm text-gray-500">Loading phrasesets…</div>
    );
  }

  if (!phrasesets.length) {
    return (
      <div className="p-6 text-center text-sm text-gray-500">
        No quips yet. Complete rounds to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {phrasesets.map((phraseset) => {
        const id = getUniqueIdForSummary(phraseset);
        const isSelected = selectedId ? selectedId === id : false;

        return (
          <button
            key={id}
            onClick={() => onSelect(phraseset)}
            className={`w-full text-left rounded-lg border transition-colors p-4 ${
              isSelected
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-blue-50'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-800">
                  {formatLabel(phraseset.prompt_text)}
                </p>
                <p className="text-xs text-gray-600 mt-1">
                  Role: {phraseset.your_role} • {phraseset.vote_count ?? 0} votes
                </p>
                {phraseset.new_activity_count > 0 && (
                  <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-1 text-[11px] font-semibold text-red-700">
                    • {phraseset.new_activity_count} new update{phraseset.new_activity_count > 1 ? 's' : ''}
                  </p>
                )}
              </div>
              <StatusBadge status={phraseset.status} />
            </div>
          </button>
        );
      })}
    </div>
  );
};
