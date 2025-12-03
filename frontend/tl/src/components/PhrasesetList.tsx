import React from 'react';

interface RoundSummary {
  round_id: string;
  prompt_text: string;
  final_coverage?: number;
  gross_payout?: number;
  created_at: string;
  status: string;
}

interface PhrasesetListProps {
  phrasesets: RoundSummary[];
  selectedId?: string | null;
  onSelect: (phraseset: RoundSummary) => void;
  isLoading?: boolean;
}

const formatLabel = (text: string) => {
  if (!text) return '—';
  return text.length > 60 ? `${text.slice(0, 57)}…` : text;
};

const formatPayoutDisplay = (payout?: number): string => {
  if (payout == null) return '—';
  return `$${payout.toFixed(2)}`;
};

const formatCoverageDisplay = (coverage?: number): string => {
  if (coverage == null) return '—';
  return `${(coverage * 100).toFixed(0)}%`;
};

export const PhrasesetList: React.FC<PhrasesetListProps> = ({
  phrasesets,
  selectedId,
  onSelect,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 text-center text-sm text-gray-500">Loading rounds…</div>
    );
  }

  if (!phrasesets.length) {
    return (
      <div className="p-6 text-center text-sm text-gray-500">
        No rounds yet. Start a round to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {phrasesets.map((round) => {
        const isSelected = selectedId ? selectedId === round.round_id : false;

        return (
          <button
            key={round.round_id}
            onClick={() => onSelect(round)}
            className={`w-full text-left rounded-lg border transition-colors p-4 ${
              isSelected
                ? 'border-ccl-navy bg-ccl-navy/5'
                : 'border-gray-200 bg-white hover:border-ccl-navy/20 hover:bg-ccl-navy/2'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-800">
                  {formatLabel(round.prompt_text)}
                </p>
                <p className="text-xs text-gray-600 mt-1">
                  Coverage: {formatCoverageDisplay(round.final_coverage)} • Payout: {formatPayoutDisplay(round.gross_payout)}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {new Date(round.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="text-right">
                <span className="inline-flex items-center rounded-full bg-ccl-navy/10 px-3 py-1 text-xs font-semibold text-ccl-navy">
                  {round.status}
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};
