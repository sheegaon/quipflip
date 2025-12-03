import React from 'react';

interface GuessDetail {
  guess_id: string;
  text: string;
  was_match: boolean;
  matched_cluster_ids: string[];
  created_at: string;
}

interface RoundDetails {
  round_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  final_coverage?: number;
  gross_payout?: number;
  status: string;
  strikes: number;
  created_at: string;
  ended_at?: string;
  guesses?: GuessDetail[];
}

interface PhrasesetDetailsProps {
  phraseset: RoundDetails | null;
  loading?: boolean;
}

const formatPayoutDisplay = (payout?: number): string => {
  if (payout == null) return '—';
  return `$${payout.toFixed(2)}`;
};

const formatCoverageDisplay = (coverage?: number): string => {
  if (coverage == null) return '—';
  return `${(coverage * 100).toFixed(0)}%`;
};

const formatDateTimeInUserZone = (dateString: string): string => {
  return new Date(dateString).toLocaleString();
};

export const PhrasesetDetails: React.FC<PhrasesetDetailsProps> = ({
  phraseset,
  loading,
}) => {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-600">
        Loading round details…
      </div>
    );
  }

  if (!phraseset) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Select a round to see more details.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold text-gray-800">{phraseset.prompt_text}</h2>
          <span className="inline-flex items-center rounded-full bg-ccl-navy/10 px-3 py-1 text-sm font-semibold text-ccl-navy">
            {phraseset.status}
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-xs text-blue-700 uppercase tracking-wide">Coverage</p>
            <p className="text-lg font-semibold text-blue-900">{formatCoverageDisplay(phraseset.final_coverage)}</p>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-xs text-green-700 uppercase tracking-wide">Payout</p>
            <p className="text-lg font-semibold text-green-900">{formatPayoutDisplay(phraseset.gross_payout)}</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-xs text-red-700 uppercase tracking-wide">Strikes Used</p>
            <p className="text-lg font-semibold text-red-900">{phraseset.strikes} / 3</p>
          </div>
        </div>
      </header>

      <section className="text-xs text-gray-600">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="font-semibold text-gray-700">Started:</span>{' '}
            {formatDateTimeInUserZone(phraseset.created_at)}
          </div>
          {phraseset.ended_at && (
            <div>
              <span className="font-semibold text-gray-700">Ended:</span>{' '}
              {formatDateTimeInUserZone(phraseset.ended_at)}
            </div>
          )}
          <div>
            <span className="font-semibold text-gray-700">Answer Pool Size:</span>{' '}
            {phraseset.snapshot_answer_count} answers
          </div>
        </div>
      </section>

      {phraseset.guesses && phraseset.guesses.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Guesses ({phraseset.guesses.length})</h3>
          <div className="overflow-hidden rounded-lg border">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Guess</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Result</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {phraseset.guesses.map((guess) => (
                  <tr key={guess.guess_id}>
                    <td className="px-4 py-2 text-gray-700">{guess.text}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          guess.was_match ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                        }`}
                      >
                        {guess.was_match ? '✓ Match' : '✗ No Match'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      {formatDateTimeInUserZone(guess.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
