import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import { gameAPI } from '../api/client';
import InitCoinDisplay from '../components/InitCoinDisplay';
import type { ResultsResponse } from '../api/types';

const Results: React.FC = () => {
  const navigate = useNavigate();
  const { setId } = useParams<{ setId: string }>();
  const { player } = useIRGame();

  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch results
  useEffect(() => {
    const fetchResults = async () => {
      if (!setId) return;

      try {
        setLoading(true);
        const response = await gameAPI.getResults(setId);
        setResults(response);
        setError(null);
      } catch (err: unknown) {
        const errorMessage = typeof err === 'object' && err !== null && 'response' in err
          ? ((err.response as { data?: { detail?: string } })?.data?.detail)
          : typeof err === 'object' && err !== null && 'message' in err
          ? (err.message as string)
          : 'Failed to fetch results';
        setError(errorMessage || 'Failed to fetch results');
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [setId]);

  // Redirect if no setId
  useEffect(() => {
    if (!setId) {
      navigate('/dashboard');
    }
  }, [setId, navigate]);

  if (loading || !results || !player) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
        <div className="max-w-2xl w-full tile-card p-8 text-center text-ir-cream">Loading results...</div>
      </div>
    );
  }

  const { set, entries, player_entry, player_vote, payout_breakdown } = results;

  // Find winner (entry with highest vote count)
  const winnerEntry = entries.length > 0
    ? entries.reduce((max, entry) =>
        entry.received_votes > max.received_votes ? entry : max
      )
    : null;

  // Sort entries by votes (descending)
  const sortedEntries = [...entries].sort((a, b) => b.received_votes - a.received_votes);

  const playerVotedForWinner = player_vote && winnerEntry && player_vote.chosen_entry_id === winnerEntry.entry_id;

  // Calculate totals from payout_breakdown if available
  const breakdown = payout_breakdown || {
    entry_cost: 0,
    vote_cost: 0,
    gross_payout: 0,
    vault_rake: 0,
    net_payout: 0,
    vote_reward: 0,
  };

  const totalCost = breakdown.entry_cost + breakdown.vote_cost;
  const totalEarnings = breakdown.gross_payout + breakdown.vote_reward;
  const netGainLoss = totalEarnings - totalCost - breakdown.vault_rake;

  return (
    <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-8 slide-up-enter tutorial-results-card">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-4xl font-display font-bold text-ir-navy mb-2">Results</h1>
          <p className="text-ir-teal text-lg mb-2">
            Word: <strong className="text-ir-orange">{set.word.toUpperCase()}</strong>
          </p>
          <p className="text-sm text-ir-teal">
            {set.entry_count} entries • {set.vote_count} votes
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Payout Summary Card */}
        {payout_breakdown && (
          <div className={`mb-6 p-6 rounded-tile shadow-tile ${netGainLoss >= 0 ? 'bg-ir-teal-light border-2 border-ir-turquoise' : 'bg-ir-cream border-2 border-ir-orange'}`}>
            <div className="text-center">
              <h2 className="text-2xl font-bold mb-2">
                {netGainLoss >= 0 ? '🎉 You Earned!' : '💸 Net Result'}
              </h2>
              <div className={`text-5xl font-bold mb-4 ${netGainLoss >= 0 ? 'text-ir-turquoise' : 'text-ir-orange'}`}>
                {netGainLoss >= 0 ? '+' : ''}
                <InitCoinDisplay amount={netGainLoss} />
              </div>

              {/* Breakdown Details */}
              <div className="mt-6 bg-white rounded-lg p-4 text-left">
                <h3 className="font-bold text-ir-navy mb-3 text-center">Transaction Breakdown</h3>
                <div className="space-y-2 text-sm text-ir-teal">
                  {/* Costs */}
                  {breakdown.entry_cost > 0 && (
                    <div className="flex justify-between">
                      <span className="text-ir-teal">Entry cost:</span>
                      <span className="text-ir-orange font-semibold">
                        -<InitCoinDisplay amount={breakdown.entry_cost} />
                      </span>
                    </div>
                  )}
                  {breakdown.vote_cost > 0 && (
                    <div className="flex justify-between">
                      <span className="text-ir-teal">Vote cost:</span>
                      <span className="text-ir-orange font-semibold">
                        -<InitCoinDisplay amount={breakdown.vote_cost} />
                      </span>
                    </div>
                  )}

                  {/* Earnings */}
                  {breakdown.gross_payout > 0 && (
                    <div className="flex justify-between">
                      <span className="text-ir-teal">Backronym payout:</span>
                      <span className="text-ir-turquoise font-semibold">
                        +<InitCoinDisplay amount={breakdown.gross_payout} />
                      </span>
                    </div>
                  )}
                  {breakdown.vote_reward > 0 && (
                    <div className="flex justify-between">
                      <span className="text-ir-teal">Correct vote reward:</span>
                      <span className="text-ir-turquoise font-semibold">
                        +<InitCoinDisplay amount={breakdown.vote_reward} />
                      </span>
                    </div>
                  )}

                  {/* Vault Rake */}
                  {breakdown.vault_rake > 0 && (
                    <div className="flex justify-between">
                      <span className="text-ir-teal">Vault contribution (30%):</span>
                      <span className="text-ir-orange font-semibold">
                        -<InitCoinDisplay amount={breakdown.vault_rake} />
                      </span>
                    </div>
                  )}

                  {/* Total */}
                  <div className="pt-2 border-t border-ir-teal border-opacity-30 flex justify-between font-bold">
                    <span className="text-ir-navy">Net:</span>
                    <span className={netGainLoss >= 0 ? 'text-ir-turquoise' : 'text-ir-orange'}>
                      {netGainLoss >= 0 ? '+' : ''}
                      <InitCoinDisplay amount={netGainLoss} />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Card */}
        <div className="tile-card p-8 mb-6">
          <h2 className="text-2xl font-bold text-ir-navy mb-6 text-center">All Backronyms</h2>

          {/* Entries List */}
          <div className="space-y-4">
            {sortedEntries.map((entry, index) => {
              const isWinner = entry.entry_id === winnerEntry?.entry_id;
              const isPlayerEntry = player_entry && entry.entry_id === player_entry.entry_id;
              const playerVotedForThis = player_vote && entry.entry_id === player_vote.chosen_entry_id;
              const votePercentage = set.vote_count > 0
                ? ((entry.received_votes / set.vote_count) * 100).toFixed(1)
                : '0.0';

              return (
                <div
                  key={entry.entry_id}
                  className={`p-6 rounded-lg border-2 relative ${
                    isWinner
                      ? 'bg-ir-orange bg-opacity-10 border-ir-orange shadow-md'
                      : isPlayerEntry
                      ? 'bg-ir-turquoise bg-opacity-10 border-ir-turquoise'
                      : 'bg-ir-cream border-ir-teal border-opacity-30'
                  }`}
                >
                  {/* Badges */}
                  <div className="absolute top-2 right-2 flex gap-2">
                    {isWinner && (
                      <div className="bg-ir-orange text-white text-xs px-3 py-1 rounded-full font-semibold">
                        👑 WINNER
                      </div>
                    )}
                    {isPlayerEntry && (
                      <div className="bg-ir-turquoise text-white text-xs px-3 py-1 rounded-full font-semibold">
                        YOURS
                      </div>
                    )}
                    {playerVotedForThis && (
                      <div className="bg-ir-teal text-white text-xs px-3 py-1 rounded-full font-semibold">
                        ✓ YOUR VOTE
                      </div>
                    )}
                    {entry.is_ai && (
                      <div className="bg-ir-navy text-white text-xs px-3 py-1 rounded-full font-semibold">
                        AI
                      </div>
                    )}
                  </div>

                  {/* Rank */}
                  <div className="text-ir-teal text-sm font-semibold mb-2">
                    #{index + 1}
                  </div>

                  {/* Backronym Display */}
                  <div className="flex flex-wrap gap-2 items-center justify-center mb-3">
                    {entry.backronym_text.map((word, wordIndex) => (
                      <React.Fragment key={wordIndex}>
                        <span className="text-2xl font-bold text-ir-navy">
                          {word}
                        </span>
                        {wordIndex < entry.backronym_text.length - 1 && (
                          <span className="text-ir-teal">•</span>
                        )}
                      </React.Fragment>
                    ))}
                  </div>

                  {/* Letter Highlight */}
                  <div className="flex justify-center gap-1 text-sm mb-4">
                    {entry.backronym_text.map((word, wordIndex) => (
                      <span
                        key={wordIndex}
                        className="font-mono font-bold text-ir-turquoise"
                      >
                        {word.charAt(0)}
                      </span>
                    ))}
                    <span className="text-ir-teal ml-2">
                      = {set.word.toUpperCase()}
                    </span>
                  </div>

                  {/* Vote Stats */}
                  <div className="bg-ir-cream rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-ir-teal">Votes received:</span>
                      <span className="font-bold text-ir-navy">
                        {entry.received_votes} ({votePercentage}%)
                      </span>
                    </div>

                    {/* Vote Progress Bar */}
                    <div className="w-full bg-ir-teal-light rounded-full h-3 overflow-hidden">
                      <div
                        className={`h-3 rounded-full transition-all ${
                          isWinner ? 'bg-ir-orange' : 'bg-ir-turquoise'
                        }`}
                        style={{ width: `${votePercentage}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Vote Summary */}
        {player_vote && (
          <div className="tile-card p-6 mb-6">
            <h3 className="text-xl font-bold text-ir-navy mb-4 text-center">Your Vote</h3>
            <div className={`p-4 rounded-lg text-center ${playerVotedForWinner ? 'bg-ir-teal-light' : 'bg-ir-cream'}`}>
              <p className="text-ir-teal">
                You voted for:{' '}
                <strong>
                  {entries.find(e => e.entry_id === player_vote.chosen_entry_id)?.backronym_text.join(' ')}
                </strong>
              </p>
              {playerVotedForWinner ? (
                <p className="text-ir-turquoise font-semibold mt-2">✓ Correct! You picked the winner!</p>
              ) : (
                <p className="text-ir-teal mt-2">The crowd chose differently this time</p>
              )}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex-1 bg-ir-navy hover:bg-ir-teal text-white font-bold py-4 px-6 rounded-lg transition-colors shadow-md"
          >
            Back to Dashboard
          </button>
          <button
            onClick={() => navigate('/create')}
            className="flex-1 bg-ir-orange hover:bg-ir-orange-deep text-white font-bold py-4 px-6 rounded-lg transition-colors shadow-md"
          >
            Play Again
          </button>
        </div>
      </div>
    </div>
  );
};

export default Results;
