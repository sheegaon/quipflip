import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { Header } from '../components/Header';
import { Pagination } from '@crowdcraft/components/Pagination.tsx';
import { quipflipBranding } from '@crowdcraft/utils/brandedMessages.ts';
import type { PhrasesetResults, PhrasesetDetails, PhrasesetVoteDetail } from '@crowdcraft/api/types.ts';
import { resultsLogger } from '@crowdcraft/utils/logger.ts';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { BotIcon, QuestionMarkIcon, ResultsIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { isAiPlayer } from '@crowdcraft/utils/ai.ts';

const { loadingMessages } = quipflipBranding;

const ITEMS_PER_PAGE = 10;
const WALLET_VS_VAULT_TITLE = 'Wallet vs. Vault';
const WALLET_VS_VAULT_DESCRIPTION =
  'Winning rounds split the net payout: about 70% goes back into your spendable wallet and the remaining 30% is skimmed into the vault leaderboard balance.';
const WALLET_VS_VAULT_NOTE =
  'Break-even or losing rounds pay entirely into the wallet, so vault growth only comes from profitable play.';

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
  const { pendingResults, phrasesetResults, phrasesetDetails } = resultsState;
  const { refreshDashboard } = gameActions;
  const { refreshPhrasesetResults, refreshPhrasesetDetails, markResultsViewed } = resultsActions;
  const [selectedPhrasesetId, setSelectedPhrasesetId] = useState<string | null>(null);
  const [expandedVotes, setExpandedVotes] = useState<Record<string, boolean>>({});
  const [isVaultInfoOpen, setIsVaultInfoOpen] = useState<boolean>(false);
  const [isPrizeBreakdownOpen, setIsPrizeBreakdownOpen] = useState<boolean>(false);
  const [isEarningsBreakdownOpen, setIsEarningsBreakdownOpen] = useState<boolean>(false);
  const [voteResultsPage, setVoteResultsPage] = useState<number>(1);
  const [latestResultsPage, setLatestResultsPage] = useState<number>(1);

  const refreshPhrasesetResultsRef = useRef(refreshPhrasesetResults);
  const refreshPhrasesetDetailsRef = useRef(refreshPhrasesetDetails);
  const refreshDashboardRef = useRef(refreshDashboard);

  useEffect(() => {
    refreshPhrasesetResultsRef.current = refreshPhrasesetResults;
  }, [refreshPhrasesetResults]);

  useEffect(() => {
    refreshPhrasesetDetailsRef.current = refreshPhrasesetDetails;
  }, [refreshPhrasesetDetails]);

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
  const currentDetailsEntry = selectedPhrasesetId ? phrasesetDetails[selectedPhrasesetId] : undefined;
  const results: PhrasesetResults | null = currentEntry?.data ?? null;
  const loading = currentEntry?.loading ?? false;
  const error = currentEntry?.error ?? null;
  const selectedDetails: PhrasesetDetails | null = currentDetailsEntry?.data ?? null;
  const detailsLoading = currentDetailsEntry?.loading ?? false;
  const detailsError = currentDetailsEntry?.error ?? null;

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

    refreshPhrasesetDetailsRef.current(selectedPhrasesetId, { force: true }).catch((err) => {
      resultsLogger.error('Failed to refresh phraseset details for results page', err);
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

  const toggleVaultInfo = () => {
    setIsVaultInfoOpen((prev) => {
      const next = !prev;
      if (next) {
        setIsPrizeBreakdownOpen(false);
      }
      return next;
    });
  };

  const togglePrizeBreakdown = () => {
    setIsPrizeBreakdownOpen((prev) => {
      const next = !prev;
      if (next) {
        setIsVaultInfoOpen(false);
        setIsEarningsBreakdownOpen(false);
      }
      return next;
    });
  };

  const toggleEarningsBreakdown = () => {
    setIsEarningsBreakdownOpen((prev) => {
      const next = !prev;
      if (next) {
        setIsVaultInfoOpen(false);
        setIsPrizeBreakdownOpen(false);
      }
      return next;
    });
  };

  useEffect(() => {
    setIsVaultInfoOpen(false);
    setIsPrizeBreakdownOpen(false);
    setIsEarningsBreakdownOpen(false);
  }, [selectedPhrasesetId]);

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

  const phraseAuthorMap = useMemo(() => {
    if (!selectedDetails) {
      return {} as Record<string, { username: string; isAi: boolean }>;
    }

    return selectedDetails.contributors.reduce<Record<string, { username: string; isAi: boolean }>>((acc, contributor) => {
      if (contributor.phrase) {
        acc[contributor.phrase] = {
          username: contributor.username,
          isAi: isAiPlayer(contributor),
        };
      }
      return acc;
    }, {});
  }, [selectedDetails]);

  const votesByPhrase = useMemo(() => {
    if (!selectedDetails) {
      return {} as Record<string, PhrasesetVoteDetail[]>;
    }

    return selectedDetails.votes.reduce<Record<string, PhrasesetVoteDetail[]>>((acc, voteDetail) => {
      if (!acc[voteDetail.voted_phrase]) {
        acc[voteDetail.voted_phrase] = [];
      }
      acc[voteDetail.voted_phrase].push(voteDetail);
      return acc;
    }, {});
  }, [selectedDetails]);

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
      <div className="min-h-screen bg-ccl-cream bg-pattern">
        <Header />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="tile-card p-8 text-center">
            <div className="flex justify-center mb-4">
              <ResultsIcon className="h-20 w-20 text-6xl"/>
            </div>
            <h1 className="text-2xl font-display font-bold text-ccl-navy mb-4">No Results Available</h1>
            <p className="text-ccl-teal mb-6">
              You don't have any finalized quipsets yet. Complete some rounds and check back!
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-ccl-navy">Results</h1>
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
                <div className="bg-ccl-navy bg-opacity-5 border-2 border-ccl-navy rounded-tile p-4 mb-6">
                  <p className="text-sm text-ccl-teal mb-1 font-medium">Prompt:</p>
                  <p className="text-xl font-display font-semibold text-ccl-navy">{results.prompt_text}</p>
                </div>

                <div className="bg-ccl-turquoise bg-opacity-10 border-2 border-ccl-turquoise rounded-tile p-4 mb-6">
                  <h3 className="font-display font-bold text-lg text-ccl-turquoise mb-3">Your Performance</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-ccl-teal">Your Phrase:</p>
                      <p className="text-xl font-bold text-ccl-navy">{results.your_phrase}</p>
                      {results.your_role === 'copy' && results.original_phrase && (
                        <div className="mt-2">
                          <p className="text-sm text-ccl-teal">Original Phrase:</p>
                          <p className="text-lg font-semibold text-ccl-navy">{results.original_phrase}</p>
                        </div>
                      )}
                    </div>
                    <div>
                      <p className="text-sm text-ccl-teal">Your Role:</p>
                      <p className="text-xl font-bold text-ccl-navy capitalize">{results.your_role}</p>
                    </div>
                    <div>
                      <p className="text-sm text-ccl-teal">Points Earned:</p>
                      <p className="text-xl font-bold text-ccl-navy">{results.your_points}</p>
                    </div>
                    <div>
                      <p className="text-sm text-ccl-teal">Total Points:</p>
                      <p className="text-xl font-bold text-ccl-navy">{results.total_points}</p>
                    </div>
                    <div className="relative">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-ccl-teal">Final Prize Pool:</p>
                        <button
                          type="button"
                          onClick={togglePrizeBreakdown}
                          className="text-ccl-turquoise hover:text-ccl-navy transition-colors"
                          aria-label="Show prize pool breakdown"
                          aria-expanded={isPrizeBreakdownOpen}
                        >
                          <QuestionMarkIcon className="h-5 w-5" />
                        </button>
                      </div>
                      <p className="text-xl font-bold text-ccl-navy">
                        <CurrencyDisplay
                          amount={results.total_pool}
                          iconClassName="w-5 h-5"
                          textClassName="text-xl font-bold text-ccl-navy"
                        />
                      </p>
                      {isPrizeBreakdownOpen && (
                        <div className="absolute right-0 top-full mt-2 w-80 max-w-xs sm:max-w-sm bg-white bg-opacity-100 border border-ccl-turquoise rounded-2xl shadow-2xl z-30">
                          <div className="p-4">
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <p className="font-semibold text-ccl-navy">Prize Pool Breakdown</p>
                              <button
                                type="button"
                                onClick={() => setIsPrizeBreakdownOpen(false)}
                                className="text-ccl-teal hover:text-ccl-navy font-bold"
                                aria-label="Close prize pool breakdown"
                              >
                                ×
                              </button>
                            </div>
                            <p className="text-xs uppercase tracking-wide text-ccl-teal mb-1">Pool math</p>
                            <p className="text-sm text-ccl-navy">{performanceBreakdown.poolShareText}</p>
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="relative">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-ccl-teal">Earnings:</p>
                        <button
                          type="button"
                          onClick={toggleEarningsBreakdown}
                          className="text-ccl-turquoise hover:text-ccl-navy transition-colors"
                          aria-label="Show earnings breakdown"
                          aria-expanded={isEarningsBreakdownOpen}
                        >
                          <QuestionMarkIcon className="h-5 w-5" />
                        </button>
                      </div>
                      <p className="text-2xl font-display font-bold text-ccl-turquoise">
                        <CurrencyDisplay
                          amount={results.your_payout}
                          iconClassName="w-6 h-6"
                          textClassName="text-2xl font-display font-bold text-ccl-turquoise"
                        />
                      </p>
                      {isEarningsBreakdownOpen && (
                        <div className="absolute right-0 top-full mt-2 w-80 max-w-xs sm:max-w-sm bg-white bg-opacity-100 border border-ccl-turquoise rounded-2xl shadow-2xl z-30">
                          <div className="p-4">
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <p className="font-semibold text-ccl-navy">Earnings Breakdown</p>
                              <button
                                type="button"
                                onClick={() => setIsEarningsBreakdownOpen(false)}
                                className="text-ccl-teal hover:text-ccl-navy font-bold"
                                aria-label="Close earnings breakdown"
                              >
                                ×
                              </button>
                            </div>
                            <p className="text-xs uppercase tracking-wide text-ccl-teal mb-1">Points</p>
                            <p className="text-sm text-ccl-navy">{performanceBreakdown.totalPointsLabel}</p>
                            <p className="text-xs uppercase tracking-wide text-ccl-teal mt-3 mb-1">Payout</p>
                            <p className="text-sm font-semibold text-ccl-turquoise">{performanceBreakdown.breakdownLine}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="mt-4 space-y-3">
                    {results.vault_skim_amount > 0 && (
                      <div className="relative">
                        {isVaultInfoOpen && (
                          <div className="absolute left-1/2 -top-3 -translate-y-full -translate-x-1/2 w-80 max-w-xs sm:max-w-sm bg-white border border-ccl-turquoise border-opacity-40 rounded-2xl shadow-2xl z-30">
                            <div className="p-4">
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <p className="font-semibold text-ccl-navy">{WALLET_VS_VAULT_TITLE}</p>
                                <button
                                  type="button"
                                  onClick={() => setIsVaultInfoOpen(false)}
                                  className="text-ccl-teal hover:text-ccl-navy font-bold"
                                  aria-label="Close wallet and vault explainer"
                                >
                                  ×
                                </button>
                              </div>
                              <p className="text-sm text-ccl-navy">{WALLET_VS_VAULT_DESCRIPTION}</p>
                              <p className="text-sm text-ccl-teal mt-2">{WALLET_VS_VAULT_NOTE}</p>
                            </div>
                          </div>
                        )}
                        <div className="p-3 bg-ccl-turquoise bg-opacity-10 rounded-tile border border-ccl-turquoise border-opacity-30">
                          <p className="text-sm text-ccl-navy text-center flex items-center justify-center gap-2">
                            <button
                              type="button"
                              onClick={toggleVaultInfo}
                              className="text-ccl-turquoise hover:text-ccl-navy transition-colors"
                              aria-label="Explain wallet and vault mechanics"
                              aria-expanded={isVaultInfoOpen}
                            >
                              <QuestionMarkIcon className="h-5 w-5" />
                            </button>
                            <span className="flex items-center gap-1">
                              <img src="/vault.png" alt="Vault" className="w-4 h-4" />
                              <span>
                                <span className="font-semibold">{results.vault_skim_amount}</span> secured in your vault
                              </span>
                            </span>
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="mb-6">
                  <h3 className="font-display font-bold text-lg text-ccl-navy mb-3">Vote Results</h3>
                  {detailsError && (
                    <p className="text-sm text-red-600 mb-3">We couldn't load all contributor info. Showing basic vote data.</p>
                  )}
                  <div className="space-y-2">
                    {voteResultsPagination.paginatedVotes.map((vote, pageIndex) => {
                      const actualIndex = voteResultsPagination.startIndex + pageIndex;
                      const author = phraseAuthorMap[vote.phrase];
                      const votesForPhrase = votesByPhrase[vote.phrase] ?? [];
                      const isExpanded = expandedVotes[vote.phrase];
                      return (
                        <div
                          key={vote.phrase}
                          className={`p-4 rounded-tile border-2 ${
                            vote.is_original
                              ? 'bg-ccl-orange bg-opacity-10 border-ccl-orange'
                              : 'bg-ccl-cream border-ccl-teal border-opacity-30'
                          }`}
                        >
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div>
                              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ccl-teal">
                                <span className="text-ccl-navy">Phrase #{actualIndex + 1}</span>
                                {vote.is_original && (
                                  <span className="bg-ccl-orange text-white px-2 py-0.5 rounded-full text-[11px]">Original</span>
                                )}
                              </div>
                              <p className="text-xl font-bold text-ccl-navy mt-1">{vote.phrase}</p>
                              <div className="flex flex-wrap items-center gap-2 text-sm text-ccl-teal mt-1">
                                <span>by {author?.username ?? 'Unknown author'}</span>
                                {author?.isAi && <BotIcon className="h-4 w-4" />}
                              </div>
                              <button
                                type="button"
                                onClick={() => toggleVotersList(vote.phrase)}
                                className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-ccl-turquoise hover:text-ccl-navy focus:outline-none"
                              >
                                {isExpanded ? 'Hide voters' : 'Show voters'}
                                <span className="text-xs font-normal text-ccl-teal">({vote.voters.length})</span>
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>
                            </div>
                            <div className="text-right">
                              <p className="text-3xl font-display font-bold text-ccl-turquoise leading-none">
                                {vote.vote_count}
                              </p>
                              <p className="text-xs text-ccl-teal">votes</p>
                            </div>
                          </div>
                          {isExpanded && (
                            <div className="mt-4 bg-white bg-opacity-80 rounded-tile border border-ccl-teal border-opacity-20 p-3">
                              {detailsLoading ? (
                                <div className="py-4">
                                  <LoadingSpinner isLoading={true} message="Loading voter details..." />
                                </div>
                              ) : votesForPhrase.length > 0 ? (
                                <div className="space-y-2">
                                  {votesForPhrase.map((voterDetail) => (
                                    <div
                                      key={voterDetail.vote_id}
                                      className={`flex items-center justify-between rounded-tile px-3 py-2 border ${
                                        voterDetail.correct
                                          ? 'bg-ccl-turquoise bg-opacity-10 border-ccl-turquoise'
                                          : 'bg-ccl-orange bg-opacity-10 border-ccl-orange'
                                      }`}
                                    >
                                      <div className="flex items-center gap-2 text-sm font-medium text-ccl-navy">
                                        <span>{voterDetail.voter_username}</span>
                                        {isAiPlayer(voterDetail) && <BotIcon className="h-3.5 w-3.5" />}
                                      </div>
                                      <span
                                        className={`text-xs font-semibold ${
                                          voterDetail.correct ? 'text-ccl-turquoise' : 'text-ccl-orange'
                                        }`}
                                      >
                                        {voterDetail.correct ? '✓ Correct' : '✗ Incorrect'}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              ) : vote.voters.length === 0 ? (
                                <p className="text-sm text-ccl-teal italic">No votes for this phrase yet.</p>
                              ) : (
                                <ul className="space-y-1">
                                  {vote.voters.map((voter, index) => (
                                    <li key={`${vote.phrase}-${voter}-${index}`} className="text-sm text-ccl-navy">
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
              <h2 className="font-display font-bold text-lg mb-4 text-ccl-navy">Latest Results</h2>
              <div className="space-y-2">
                {latestResultsPagination.paginatedResults.map((result) => (
                  <button
                    key={getResultKey(result)}
                    onClick={() => handleSelectPhraseset(result.phraseset_id)}
                    className={`w-full text-left p-3 rounded-tile transition-all ${
                      selectedPhrasesetId === result.phraseset_id
                        ? 'bg-ccl-turquoise bg-opacity-10 border-2 border-ccl-turquoise'
                        : 'bg-ccl-cream hover:bg-ccl-turquoise hover:bg-opacity-5 border-2 border-transparent'
                    }`}
                  >
                    <p className="text-sm font-semibold text-ccl-navy truncate">
                      {result.prompt_text}
                    </p>
                    <p className="text-xs text-ccl-teal mt-1">
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
