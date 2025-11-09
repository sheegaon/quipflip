import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Header } from '../components/Header';
import { Pagination } from '../components/Pagination';
import { loadingMessages } from '../utils/brandedMessages';
import type { PhrasesetResults } from '../api/types';
import { resultsLogger } from '../utils/logger';

const ITEMS_PER_PAGE = 10;

// Helper function to generate unique key for each result
const getResultKey = (result: { phraseset_id: string; role: string; prompt_round_id?: string; copy_round_id?: string }) => {
  if (result.role === 'prompt' && result.prompt_round_id) {
    return `${result.phraseset_id}-prompt-${result.prompt_round_id}`;
  } else if (result.role === 'copy' && result.copy_round_id) {
    return `${result.phraseset_id}-copy-${result.copy_round_id}`;
  }
  // Fallback for results without round IDs
  return `${result.phraseset_id}-${result.role}`;
};

export const Results: React.FC = () => {
  const { actions: gameActions } = useGame();
  const { state: resultsState, actions: resultsActions } = useResults();
  const { pendingResults, phrasesetResults } = resultsState;
  const { refreshDashboard } = gameActions;
  const { refreshPhrasesetResults, markResultsViewed } = resultsActions;
  const [selectedPhrasesetId, setSelectedPhrasesetId] = useState<string | null>(null);
  const [expandedVotes, setExpandedVotes] = useState<Record<string, boolean>>({});
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);
  const [voteResultsPage, setVoteResultsPage] = useState<number>(1);
  const [latestResultsPage, setLatestResultsPage] = useState<number>(1);

  const refreshPhrasesetResultsRef = useRef(refreshPhrasesetResults);
  const refreshDashboardRef = useRef(refreshDashboard);

  useEffect(() => {
    refreshPhrasesetResultsRef.current = refreshPhrasesetResults;
  }, [refreshPhrasesetResults]);

  useEffect(() => {
    refreshDashboardRef.current = refreshDashboard;
  }, [refreshDashboard]);

  // Mark all results as viewed when page is first visited
  const hasMarkedAllViewedRef = useRef(false);
  useEffect(() => {
    if (pendingResults.length > 0 && !hasMarkedAllViewedRef.current) {
      hasMarkedAllViewedRef.current = true;
      const allIds = pendingResults.map(r => r.phraseset_id);
      markResultsViewed(allIds);
      resultsLogger.debug('Results page visited - marking all results as viewed', {
        count: allIds.length,
        ids: allIds
      });
    }
  }, [pendingResults, markResultsViewed]);

  useEffect(() => {
    resultsLogger.debug('Results page mounted', {
      pendingResults: pendingResults.length,
    });
  }, [pendingResults.length]);

  useEffect(() => {
    if (pendingResults.length > 0 && !selectedPhrasesetId) {
      const initialId = pendingResults[0].phraseset_id;
      setSelectedPhrasesetId(initialId);
      resultsLogger.debug('Defaulting to first pending result', { initialId });
    }
  }, [pendingResults, selectedPhrasesetId]);

  const currentEntry = selectedPhrasesetId ? phrasesetResults[selectedPhrasesetId] : undefined;
  const results: PhrasesetResults | null = currentEntry?.data ?? null;
  const loading = currentEntry?.loading ?? false;
  const error = currentEntry?.error ?? null;

  useEffect(() => {
    if (!selectedPhrasesetId) return;

    resultsLogger.debug('Forcing phraseset results refresh on selection', { selectedPhrasesetId });
    refreshPhrasesetResultsRef.current(selectedPhrasesetId, { force: true })
      .then(async () => {
        await refreshDashboardRef.current();
        resultsLogger.debug('Phraseset results fetched, dashboard refresh triggered', { selectedPhrasesetId });
      })
      .catch((err) => {
        resultsLogger.error('Failed to refresh phraseset results', err);
      });
  }, [selectedPhrasesetId]);

  const handleSelectPhraseset = (phrasesetId: string) => {
    setSelectedPhrasesetId(phrasesetId);
    setVoteResultsPage(1); // Reset to first page when switching phrasesets
    markResultsViewed([phrasesetId]);
    resultsLogger.debug('Phraseset selected', { phrasesetId });
  };

  const toggleVotersList = (phrase: string) => {
    setExpandedVotes((prev) => ({
      ...prev,
      [phrase]: !prev[phrase],
    }));
  };

  const toggleBreakdown = () => {
    setShowBreakdown((prev) => !prev);
  };

  const performanceBreakdown = useMemo(() => {
    if (!results) {
      return {
        poolShareText: '',
        totalPointsLabel: '',
        breakdownLine: '',
      };
    }

    const {
      correct_vote_count,
      incorrect_vote_count,
      correct_vote_points,
      incorrect_vote_points,
      total_points,
      total_pool,
      your_points,
      your_payout,
      prize_pool_base,
      vote_cost,
      vote_payout_correct,
      second_copy_contribution,
    } = results;

    const voteTypeEmoji: Record<'correct' | 'incorrect', string> = {
      correct: '✅',
      incorrect: '❌',
    };

    const formatPointsTerm = (
      count: number,
      pointsPerVote: number,
      descriptor: 'correct' | 'incorrect',
    ) => {
      const voteWord = count === 1 ? 'vote' : 'votes';
      const pointSuffix = pointsPerVote === 1 ? 'pt' : 'pts';
      const emoji = voteTypeEmoji[descriptor];
      return `${count.toLocaleString()} ${emoji} ${voteWord} × ${pointsPerVote.toLocaleString()} ${pointSuffix}`;
    };

    const pointTerms: string[] = [];
    if (correct_vote_count > 0) {
      pointTerms.push(
        formatPointsTerm(correct_vote_count, correct_vote_points, 'correct'),
      );
    }
    if (incorrect_vote_count > 0) {
      pointTerms.push(
        formatPointsTerm(incorrect_vote_count, incorrect_vote_points, 'incorrect'),
      );
    }

    const pointsBreakdownBase =
      pointTerms.length > 0
        ? `${pointTerms.join(' + ')} = ${total_points.toLocaleString()} total pts`
        : `${total_points.toLocaleString()} total pts`;

    const pointsBreakdown =
      total_points === 0
        ? `${pointsBreakdownBase} (prize pool split evenly)`
        : pointsBreakdownBase;

    const poolTerms: string[] = [];
    poolTerms.push(`${prize_pool_base.toLocaleString()} FC base`);

    // Add second copy contribution if present
    if (second_copy_contribution > 0) {
      poolTerms.push(`+ ${second_copy_contribution.toLocaleString()} FC (2nd copy from same player)`);
    }

    const formatContributionTerm = (
      count: number,
      perVoteEffect: number,
      descriptor: 'correct' | 'incorrect',
    ) => {
      const voteWord = count === 1 ? 'vote' : 'votes';
      const sign = perVoteEffect < 0 ? '-' : '+';
      const magnitude = Math.abs(perVoteEffect).toLocaleString();
      const emoji = voteTypeEmoji[descriptor];
      return `${sign} ${count.toLocaleString()} ${emoji} ${voteWord} × ${magnitude} FC`;
    };

    const correctPerVoteEffect = vote_cost - vote_payout_correct;
    const incorrectPerVoteEffect = vote_cost;

    if (correct_vote_count > 0) {
      poolTerms.push(
        formatContributionTerm(correct_vote_count, correctPerVoteEffect, 'correct'),
      );
    }
    if (incorrect_vote_count > 0) {
      poolTerms.push(
        formatContributionTerm(incorrect_vote_count, incorrectPerVoteEffect, 'incorrect'),
      );
    }

    const poolBreakdown = `${poolTerms.join(' ')} = ${total_pool.toLocaleString()} FC`;

    let earningsLine: string;
    if (total_points === 0) {
      earningsLine = `Earnings: ${your_payout.toLocaleString()} FC (split evenly)`;
    } else {
      const ratio = `${your_points.toLocaleString()} / ${total_points.toLocaleString()}`;
      earningsLine = `Earnings: ${total_pool.toLocaleString()} FC x (${ratio}) = ${your_payout.toLocaleString()} FC`;
    }

    return {
      poolShareText: poolBreakdown,
      totalPointsLabel: pointsBreakdown,
      breakdownLine: earningsLine,
    };
  }, [results]);

  // Memoized vote results pagination
  const voteResultsPagination = useMemo(() => {
    if (!results) {
      return {
        paginatedVotes: [],
        totalPages: 0,
        startIndex: 0,
      };
    }

    const sortedVotes = [...results.votes].sort((a, b) => b.vote_count - a.vote_count);
    const totalPages = Math.ceil(sortedVotes.length / ITEMS_PER_PAGE);
    const startIndex = (voteResultsPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const paginatedVotes = sortedVotes.slice(startIndex, endIndex);

    return {
      paginatedVotes,
      totalPages,
      startIndex,
    };
  }, [results, voteResultsPage]);

  // Memoized latest results pagination
  const latestResultsPagination = useMemo(() => {
    const totalPages = Math.ceil(pendingResults.length / ITEMS_PER_PAGE);
    const startIndex = (latestResultsPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const paginatedResults = pendingResults.slice(startIndex, endIndex);

    return {
      paginatedResults,
      totalPages,
    };
  }, [pendingResults, latestResultsPage]);

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
          <div className="lg:col-span-2">
            {loading && (
              <div className="tile-card p-8 flex justify-center">
                <LoadingSpinner isLoading={true} message={loadingMessages.loading} />
              </div>
            )}

            {error && !loading && (
              <div className="bg-white rounded-lg shadow-lg p-8">
                <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                  {error}
                </div>
              </div>
            )}

            {results && !loading && !error && (
              <div className="tile-card p-6 slide-up-enter">
                <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-4 mb-6">
                  <p className="text-sm text-quip-teal mb-1 font-medium">Prompt:</p>
                  <p className="text-xl font-display font-semibold text-quip-navy">{results.prompt_text}</p>
                </div>

                <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4 mb-6">
                  <h3 className="font-display font-bold text-lg text-quip-turquoise mb-3">Your Performance</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-quip-teal">Your Phrase:</p>
                      <p className="text-xl font-bold text-quip-navy">{results.your_phrase}</p>
                      {results.your_role === 'copy' && results.original_phrase && (
                        <div className="mt-2">
                          <p className="text-sm text-quip-teal">Original Phrase:</p>
                          <p className="text-lg font-semibold text-quip-navy">{results.original_phrase}</p>
                        </div>
                      )}
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
                      <p className="text-sm text-quip-teal">Total Points:</p>
                      <p className="text-xl font-bold text-quip-navy">{results.total_points}</p>
                    </div>
                    <div>
                      <p className="text-sm text-quip-teal">Final Prize Pool:</p>
                      <p className="text-xl font-bold text-quip-navy">{results.total_pool} FC</p>
                    </div>
                    <div>
                      <p className="text-sm text-quip-teal">Earnings:</p>
                      <p className="text-2xl font-display font-bold text-quip-turquoise">
                        {results.your_payout} FC
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="p-3 bg-quip-turquoise bg-opacity-5 rounded-tile border border-quip-turquoise border-opacity-20">
                      <p className="text-sm text-quip-teal text-center">
                        ✓ Automatically added to your balance when voting completed
                      </p>
                    </div>
                    <div className="p-4 bg-white bg-opacity-80 rounded-tile border border-quip-turquoise border-opacity-20">
                      <button
                        type="button"
                        onClick={toggleBreakdown}
                        className="text-sm font-medium text-quip-turquoise hover:text-quip-navy focus:outline-none"
                      >
                        {showBreakdown ? 'Hide Prize Pool Breakdown' : 'Show Prize Pool Breakdown'}
                      </button>
                      {showBreakdown && (
                        <div className="mt-2">
                          <p className="text-sm text-quip-teal font-medium">Prize Pool Breakdown</p>
                          <p className="text-sm text-quip-navy">{performanceBreakdown.poolShareText}</p>
                          <p className="text-sm text-quip-navy">{performanceBreakdown.totalPointsLabel}</p>
                          <p className="text-sm font-semibold text-quip-turquoise">{performanceBreakdown.breakdownLine}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mb-6">
                  <h3 className="font-display font-bold text-lg text-quip-navy mb-3">Vote Results</h3>
                  <div className="space-y-2">
                    {voteResultsPagination.paginatedVotes.map((vote, pageIndex) => {
                      const actualIndex = voteResultsPagination.startIndex + pageIndex;
                      return (
                        <div
                          key={vote.phrase}
                          className={`p-4 rounded-tile border-2 ${
                            vote.is_original
                              ? 'bg-quip-orange bg-opacity-10 border-quip-orange'
                              : 'bg-quip-cream border-quip-teal border-opacity-30'
                          }`}
                        >
                          <div className="flex justify-between items-start gap-4">
                            <div className="flex items-start gap-3">
                              <span className="text-2xl font-display font-bold text-quip-teal text-opacity-50">
                                #{actualIndex + 1}
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
                                <button
                                  type="button"
                                  onClick={() => toggleVotersList(vote.phrase)}
                                  className="mt-2 inline-flex items-center text-sm font-medium text-quip-turquoise hover:text-quip-navy focus:outline-none"
                                >
                                  {expandedVotes[vote.phrase] ? 'Hide voters' : 'Show voters'} ({vote.voters.length})
                                </button>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-display font-bold text-quip-turquoise">
                                {vote.vote_count}
                              </p>
                              <p className="text-xs text-quip-teal">votes</p>
                            </div>
                          </div>
                          {expandedVotes[vote.phrase] && (
                            <div className="mt-4 bg-white bg-opacity-80 rounded-tile border border-quip-teal border-opacity-20 p-3">
                              {vote.voters.length === 0 ? (
                                <p className="text-sm text-quip-teal italic">No votes for this phrase yet.</p>
                              ) : (
                                <ul className="space-y-1">
                                  {vote.voters.map((voter, index) => (
                                    <li key={`${vote.phrase}-${voter}-${index}`} className="text-sm text-quip-navy">
                                      {voter}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                    <Pagination
                      currentPage={voteResultsPage}
                      totalPages={voteResultsPagination.totalPages}
                      onPageChange={setVoteResultsPage}
                    />
                  </div>
                </div>

                {/* Removed Final Rankings section since rankings property doesn't exist in PhrasesetResults */}
              </div>
            )}
          </div>

          <div className="lg:col-span-1">
            <div className="tile-card p-4">
              <h2 className="font-display font-bold text-lg mb-4 text-quip-navy">Latest Results</h2>
              <div className="space-y-2">
                {latestResultsPagination.paginatedResults.map((result) => (
                  <button
                    key={getResultKey(result)}
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
                      Role: {result.role} • {result.result_viewed ? 'Viewed' : '✨ New!'}
                    </p>
                  </button>
                ))}
              </div>
              {pendingResults.length > 0 && (
                <Pagination
                  currentPage={latestResultsPage}
                  totalPages={latestResultsPagination.totalPages}
                  onPageChange={setLatestResultsPage}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Results;
