import React, { useState, useEffect } from 'react';
import { useGame } from '../contexts/GameContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Header } from '../components/Header';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import apiClient, { extractErrorMessage } from '../api/client';
import { loadingMessages } from '../utils/brandedMessages';
import type { PhrasesetResults } from '../api/types';

export const Results: React.FC = () => {
  const { state, actions } = useGame();
  const { pendingResults } = state;
  const { refreshDashboard, getPhrasesetResults } = actions;
  const [selectedPhrasesetId, setSelectedPhrasesetId] = useState<string | null>(null);
  const [results, setResults] = useState<PhrasesetResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState(false);
  const [showClaimAnimation, setShowClaimAnimation] = useState(false);

  useEffect(() => {
    // Auto-select first pending result if available
    if (pendingResults.length > 0 && !selectedPhrasesetId) {
      setSelectedPhrasesetId(pendingResults[0].phraseset_id);
    }
  }, [pendingResults, selectedPhrasesetId]);

  useEffect(() => {
    const fetchResults = async () => {
      if (!selectedPhrasesetId) return;

      try {
        setLoading(true);
        setError(null);
        const data = await getPhrasesetResults(selectedPhrasesetId);
        setResults(data);
        // Refresh dashboard to update pending results and balance (in case payout was collected)
        await refreshDashboard();
      } catch (err) {
        setError(extractErrorMessage(err) || 'Unable to load the results for this round. It may still be in progress or no longer available.');
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [selectedPhrasesetId, getPhrasesetResults, refreshDashboard]);

  const handleSelectPhraseset = (phrasesetId: string) => {
    setSelectedPhrasesetId(phrasesetId);
  };

  const handleClaim = async () => {
    if (!selectedPhrasesetId || claiming) return;

    try {
      setClaiming(true);
      setShowClaimAnimation(true);
      await apiClient.claimPhrasesetPrize(selectedPhrasesetId);

      // Refresh dashboard and results
      await refreshDashboard();

      // Refresh the current results to update the claimed status
      const data = await apiClient.getPhrasesetResults(selectedPhrasesetId);
      setResults(data);

      // Hide animation after a short delay
      setTimeout(() => {
        setShowClaimAnimation(false);
      }, 1000);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to claim the payout. Please try again.');
      setShowClaimAnimation(false);
    } finally {
      setClaiming(false);
    }
  };

  if (pendingResults.length === 0) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="tile-card p-8 text-center">
            <div className="text-6xl mb-4">📊</div>
            <h1 className="text-2xl font-display font-bold text-quip-navy mb-4">No Results Available</h1>
            <p className="text-quip-teal mb-6">
              You don't have any finalized quipsets yet. Complete some rounds and check back!
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Results</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Pending Results List */}
          <div className="lg:col-span-1">
            <div className="tile-card p-4">
              <h2 className="font-display font-bold text-lg mb-4 text-quip-navy">Pending Results</h2>
              <div className="space-y-2">
                {pendingResults.map((result) => (
                  <button
                    key={result.phraseset_id}
                    onClick={() => handleSelectPhraseset(result.phraseset_id)}
                    className={`w-full text-left p-3 rounded-tile transition-all ${
                      selectedPhrasesetId === result.phraseset_id
                        ? 'bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise'
                        : 'bg-quip-cream hover:bg-quip-turquoise hover:bg-opacity-5 border-2 border-transparent'
                    }`}
                  >
                    <p className="text-sm font-semibold text-quip-navy truncate">
                      {result.prompt_text}
                    </p>
                    <p className="text-xs text-quip-teal mt-1">
                      Role: {result.role} • {result.payout_claimed ? 'Claimed' : '✨ New!'}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Results Details */}
          <div className="lg:col-span-2">
            {loading && (
              <div className="tile-card p-8 flex justify-center">
                <LoadingSpinner isLoading={true} message={loadingMessages.loading} />
              </div>
            )}

            {error && (
              <div className="bg-white rounded-lg shadow-lg p-8">
                <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                  {error}
                </div>
              </div>
            )}

            {results && !loading && (
              <div className="tile-card p-6 slide-up-enter">
                {/* Prompt */}
                <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-4 mb-6">
                  <p className="text-sm text-quip-teal mb-1 font-medium">Prompt:</p>
                  <p className="text-xl font-display font-semibold text-quip-navy">{results.prompt_text}</p>
                </div>

                {/* Your Performance */}
                <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4 mb-6">
                  <h3 className="font-display font-bold text-lg text-quip-turquoise mb-3">Your Performance</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-quip-teal">Your Phrase:</p>
                      <p className="text-xl font-bold text-quip-navy">{results.your_phrase}</p>
                    </div>
                    <div>
                      <p className="text-sm text-quip-teal">Your Role:</p>
                      <p className="text-xl font-bold text-quip-navy capitalize">{results.your_role}</p>
                    </div>
                    <div>
                      <p className="text-sm text-quip-teal">Points Earned:</p>
                      <p className="text-xl font-bold text-quip-navy">{results.your_points}</p>
                    </div>
                    <div>
                      <p className="text-sm text-quip-teal">Payout:</p>
                      <p className="text-2xl font-display font-bold text-quip-turquoise relative">
                        {showClaimAnimation && (
                          <span className="absolute inset-0 flex items-center justify-center">
                            <img src="/flipcoin.png" alt="" className="w-8 h-8 balance-flip-active" />
                          </span>
                        )}
                        {results.your_payout} FC
                      </p>
                    </div>
                  </div>
                  {results.already_collected ? (
                    <p className="text-sm text-quip-teal mt-3 italic">
                      ✓ Payout already collected
                    </p>
                  ) : (
                    <button
                      onClick={handleClaim}
                      disabled={claiming}
                      className="mt-4 w-full bg-quip-turquoise hover:bg-quip-teal disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm inline-flex items-center justify-center gap-2"
                    >
                      {claiming ? (
                        <>
                          <img src="/flipcoin.png" alt="" className="w-6 h-6 balance-flip-active" />
                          Claiming...
                        </>
                      ) : (
                        <>
                          <img src="/flipcoin.png" alt="" className="w-6 h-6" />
                          Claim {results.your_payout} FC
                        </>
                      )}
                    </button>
                  )}
                </div>

                {/* Vote Results */}
                <div className="mb-6">
                  <h3 className="font-display font-bold text-lg text-quip-navy mb-3">Vote Results</h3>
                  <div className="space-y-2">
                    {results.votes
                      .sort((a, b) => b.vote_count - a.vote_count)
                      .map((vote, index) => (
                        <div
                          key={vote.phrase}
                          className={`p-4 rounded-tile border-2 ${
                            vote.is_original
                              ? 'bg-quip-orange bg-opacity-10 border-quip-orange'
                              : 'bg-quip-cream border-quip-teal border-opacity-30'
                          }`}
                        >
                          <div className="flex justify-between items-center">
                            <div className="flex items-center gap-3">
                              <span className="text-2xl font-display font-bold text-quip-teal text-opacity-50">
                                #{index + 1}
                              </span>
                              <div>
                                <p className="text-xl font-bold text-quip-navy">
                                  {vote.phrase}
                                  {vote.is_original && (
                                    <span className="ml-2 text-sm bg-quip-orange text-white px-2 py-1 rounded-lg font-medium">
                                      ORIGINAL
                                    </span>
                                  )}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-display font-bold text-quip-turquoise">
                                {vote.vote_count}
                              </p>
                              <p className="text-sm text-quip-teal">votes</p>
                            </div>
                          </div>
                          {/* Vote bar */}
                          <div className="mt-2 bg-quip-navy bg-opacity-10 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${
                                vote.is_original ? 'bg-quip-orange' : 'bg-quip-turquoise'
                              }`}
                              style={{
                                width: `${(vote.vote_count / results.total_votes) * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Summary */}
                <div className="bg-quip-navy bg-opacity-5 rounded-tile p-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-quip-teal">Total Votes:</p>
                      <p className="font-bold text-quip-navy">{results.total_votes}</p>
                    </div>
                    <div>
                      <p className="text-quip-teal">Prize Pool:</p>
                      <p className="font-bold text-quip-navy">
                        <CurrencyDisplay amount={results.total_pool} iconClassName="w-4 h-4" textClassName="font-bold" />
                      </p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-quip-teal">Finalized At:</p>
                      <p className="font-bold text-quip-navy">
                        {new Date(results.finalized_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
