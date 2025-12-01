import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import { gameAPI } from '@crowdcraft/api/client.ts';
import Timer from '../components/Timer';
import InitCoinDisplay from '../components/InitCoinDisplay';
import type { BackronymSet, BackronymEntry } from '@crowdcraft/api/types.ts';
import { getErrorMessage } from '../utils/errorHelpers';

// Fisher-Yates shuffle algorithm
const shuffleArray = <T,>(array: T[]): T[] => {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
};

const Voting: React.FC = () => {
  const navigate = useNavigate();
  const { setId } = useParams<{ setId: string }>();
  const { player, submitVote, hasVoted, isAuthenticated } = useIRGame();

  const [set, setSet] = useState<BackronymSet | null>(null);
  const [shuffledEntries, setShuffledEntries] = useState<BackronymEntry[]>([]);
  const [playerEntry, setPlayerEntry] = useState<BackronymEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [hasVotedInSession, setHasVotedInSession] = useState(false);
  const pollingIntervalRef = useRef<number | null>(null);
  const hasNavigatedRef = useRef(false);
  const hasShuffledRef = useRef(false);

  // Fetch set details
  const fetchSetDetails = async () => {
    if (!setId || hasNavigatedRef.current) return;

    try {
      const response = await gameAPI.getSetStatus(setId);
      setSet(response.set);

      // Fetch entries if we're in voting status or if user has voted (for vote tracking)
      if (response.set.status === 'voting') {
        // Get full results to access entries
        const resultsResponse = await gameAPI.getResults(setId);
        setPlayerEntry(resultsResponse.player_entry || null);

        // Shuffle entries only once
        if (!hasShuffledRef.current && resultsResponse.entries.length > 0) {
          const shuffled = shuffleArray(resultsResponse.entries);
          setShuffledEntries(shuffled);
          hasShuffledRef.current = true;
        } else if (hasVotedInSession && resultsResponse.entries.length > 0) {
          // Update entries to show live vote counts
          setShuffledEntries(prevEntries => {
            return prevEntries.map(entry => {
              const updatedEntry = resultsResponse.entries.find(e => e.entry_id === entry.entry_id);
              return updatedEntry || entry;
            });
          });
        }
      }

      // Auto-navigate to results when finalized
      if (response.set.status === 'finalized' && !hasNavigatedRef.current) {
        hasNavigatedRef.current = true;
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
        setTimeout(() => {
          navigate(`/results/${setId}`);
        }, 1500);
      }

      setLoading(false);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to fetch set details'));
      setLoading(false);
    }
  };

  // Initial fetch on mount
  useEffect(() => {
    if (setId) {
      fetchSetDetails();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setId]);

  // Start polling every 3 seconds to check for finalization
  useEffect(() => {
    // Only start polling if authenticated
    if (!isAuthenticated || !setId || hasNavigatedRef.current) {
      return;
    }

    pollingIntervalRef.current = setInterval(() => {
      fetchSetDetails();
    }, 3000); // Poll every 3 seconds

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [setId, isAuthenticated]); // Key: depend on auth state

  // Redirect if no setId
  useEffect(() => {
    if (!setId) {
      navigate('/dashboard');
    }
  }, [setId, navigate]);

  // Redirect if already voted (from context, not this session)
  useEffect(() => {
    if (hasVoted && setId && !hasVotedInSession) {
      // User voted in a previous session, show vote tracking view
      setHasVotedInSession(true);
    }
  }, [hasVoted, setId, hasVotedInSession]);

  if (loading || !set || !player) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
        <div className="max-w-2xl w-full tile-card p-6 md:p-8 text-center text-ir-cream">
          Loading voting options...
        </div>
      </div>
    );
  }

  const voteCost = 10; // From config - for non-participants
  const isParticipant = playerEntry !== null;

  // Handle vote submission
  const handleVote = async (entryId: string) => {
    if (isSubmitting) return;

    // Don't allow voting for own entry
    if (playerEntry && entryId === playerEntry.entry_id) {
      setError('You cannot vote for your own backronym!');
      return;
    }

    setSelectedEntryId(entryId);

    // Show confirmation for non-participants
    if (!isParticipant) {
      const confirmed = window.confirm(
        `Voting will cost ${voteCost} InitCoins. You'll earn 20 IC if you pick the winner. Continue?`
      );
      if (!confirmed) {
        setSelectedEntryId(null);
        return;
      }
    }

    try {
      setIsSubmitting(true);
      setError(null);

      await submitVote(setId!, entryId);

      // Show vote tracking view instead of navigating to results
      setHasVotedInSession(true);
      setIsSubmitting(false);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to submit vote'));
      setIsSubmitting(false);
      setSelectedEntryId(null);
    }
  };

  // Check if set is transitioning to finalized
  const isTransitioning = set.status === 'finalized' || hasNavigatedRef.current;

  return (
    <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
      <div className="max-w-4xl w-full tile-card p-6 md:p-8 slide-up-enter tutorial-voting-card">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-display font-bold text-ir-navy mb-2">Vote for the Best Backronym</h1>
          <p className="text-ir-teal mb-2">
            Word: <strong className="text-ir-orange">{set.word.toUpperCase()}</strong>
          </p>
          {isParticipant ? (
            <p className="text-sm text-ir-turquoise">
              You're a participant - voting is free!
            </p>
          ) : (
            <p className="text-sm text-ir-orange-deep">
              Non-participant vote costs {voteCost} IC (earn 20 IC if you pick the winner)
            </p>
          )}
        </div>

        {/* Main Card */}
        <div className="bg-white rounded-tile shadow-tile p-6 md:p-8 border-2 border-ir-navy border-opacity-10">
            {/* Transitioning Message */}
            {isTransitioning && (
              <div className="mb-6 p-5 md:p-6 bg-ir-teal-light border-2 border-ir-turquoise rounded-tile text-center">
                <div className="text-2xl font-bold text-ir-turquoise mb-2">
                  ✓ Voting Complete!
                </div>
                <p className="text-ir-teal">Moving to results...</p>
              </div>
            )}

            {/* Timer Section */}
            {set.voting_finalized_at && !isTransitioning && (
              <div className="mb-6 text-center">
                <p className="text-sm text-ir-teal mb-3 font-semibold">Time remaining to vote:</p>
                <Timer
                  targetTime={set.voting_finalized_at}
                  onExpire={() => {
                    // Timer expired, AI will fill remaining votes
                    // Continue polling to detect when set moves to finalized
                  }}
                />
                <p className="text-xs text-ir-teal mt-3">
                  When time expires, AI voters will complete the voting process
                </p>
              </div>
            )}

            {/* Error Message */}
            {error && !isTransitioning && (
              <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            {/* Vote Tracking View - shown after user has voted */}
            {!isTransitioning && hasVotedInSession && (
              <>
                <div className="mb-6 p-6 bg-ir-teal-light border-2 border-ir-turquoise rounded-tile text-center">
                  <div className="text-2xl font-bold text-ir-turquoise mb-2">
                    ✓ Vote Submitted!
                  </div>
                  <p className="text-ir-teal">Waiting for other players to vote...</p>
                </div>

                {/* Vote Count Progress */}
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-lg font-semibold text-ir-navy">
                      Voting Progress
                    </h3>
                    <span className="text-xl font-bold text-ir-orange-deep">
                      {set.vote_count} / 5 votes
                    </span>
                  </div>
                  <div className="w-full bg-ir-warm-ivory rounded-full h-4 overflow-hidden border border-ir-navy border-opacity-10">
                    <div
                      className="bg-gradient-to-r from-ir-turquoise to-ir-teal h-4 rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${(set.vote_count / 5) * 100}%` }}
                    />
                  </div>
                </div>

                {/* Live Vote Counts */}
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-ir-navy mb-4 text-center">Live Vote Counts</h3>
                  <div className="space-y-3">
                    {shuffledEntries.map((entry) => {
                      const isOwnEntry = playerEntry ? entry.entry_id === playerEntry.entry_id : false;
                      const isSelectedVote = selectedEntryId === entry.entry_id;

                      return (
                        <div
                          key={entry.entry_id}
                          className={`p-4 rounded-lg border-2 ${
                            isSelectedVote
                              ? 'bg-ir-turquoise bg-opacity-20 border-ir-turquoise'
                              : 'bg-white border-ir-navy border-opacity-20'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex flex-wrap gap-2 items-center flex-1">
                              {entry.backronym_text.map((word, wordIndex) => (
                                <React.Fragment key={wordIndex}>
                                  <span className="text-lg font-bold text-gray-800">
                                    {word}
                                  </span>
                                  {wordIndex < entry.backronym_text.length - 1 && (
                                    <span className="text-gray-400">•</span>
                                  )}
                                </React.Fragment>
                              ))}
                            </div>
                            <div className="flex items-center gap-2 ml-4">
                              {isOwnEntry && (
                                <span className="bg-gray-600 text-white text-xs px-2 py-1 rounded-full font-semibold">
                                  YOU
                                </span>
                              )}
                              {isSelectedVote && (
                                <span className="bg-ir-turquoise text-white text-xs px-2 py-1 rounded-full font-semibold">
                                  YOUR VOTE
                                </span>
                              )}
                              <span className="text-2xl font-bold text-ir-orange-deep">
                                {entry.received_votes}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Info */}
                <div className="border-t border-ir-navy border-opacity-10 pt-6">
                  <div className="bg-ir-teal-light border-l-4 border-ir-turquoise p-4 rounded-tile">
                    <p className="text-sm text-ir-teal">
                      <strong>What's happening:</strong> We're waiting for all players to vote.
                      When all votes are in or the timer expires, you'll automatically see the final results!
                    </p>
                  </div>
                </div>
              </>
            )}

            {/* Voting Options - shown before user has voted */}
            {!isTransitioning && !hasVotedInSession && (
              <>
                <div className="mb-6">
                  <p className="text-center text-gray-700 font-semibold mb-4">
                    Choose the most creative backronym:
                  </p>

                  <div className="space-y-4">
                    {shuffledEntries.map((entry) => {
                      const isOwnEntry = playerEntry ? entry.entry_id === playerEntry.entry_id : false;
                      const isSelected = selectedEntryId === entry.entry_id;

                          return (
                            <button
                              key={entry.entry_id}
                              onClick={() => !isOwnEntry && handleVote(entry.entry_id)}
                              disabled={isSubmitting || isOwnEntry}
                              className={`w-full p-5 md:p-6 rounded-lg border-2 transition-all text-left relative ${
                                isOwnEntry
                                  ? 'bg-gray-100 border-gray-300 cursor-not-allowed opacity-75'
                                  : isSelected
                                  ? 'bg-ir-teal-light border-ir-turquoise shadow-md'
                                  : 'bg-white border-ir-navy border-opacity-20 hover:border-ir-turquoise hover:shadow-md'
                          } ${isSubmitting && !isSelected ? 'opacity-50' : ''}`}
                        >
                          {/* Own Entry Badge */}
                          {isOwnEntry && (
                            <div className="absolute top-2 right-2 bg-gray-600 text-white text-xs px-3 py-1 rounded-full font-semibold">
                              YOURS
                            </div>
                          )}

                          {/* Backronym Display */}
                          <div className="flex flex-wrap gap-2 items-center justify-center mb-3">
                            {entry.backronym_text.map((word, wordIndex) => (
                              <React.Fragment key={wordIndex}>
                                <span className="text-2xl font-bold text-gray-800">
                                  {word}
                                </span>
                                {wordIndex < entry.backronym_text.length - 1 && (
                                  <span className="text-gray-400">•</span>
                                )}
                              </React.Fragment>
                            ))}
                          </div>

                          {/* Letter Highlight */}
                          <div className="flex justify-center gap-1 text-sm">
                            {entry.backronym_text.map((word, wordIndex) => (
                              <span
                                key={wordIndex}
                                className="font-mono font-bold text-ir-orange"
                              >
                                {word.charAt(0)}
                              </span>
                            ))}
                            <span className="text-gray-400 ml-2">
                              = {set.word.toUpperCase()}
                            </span>
                          </div>

                          {/* Submitting indicator */}
                          {isSelected && isSubmitting && (
                            <div className="mt-4 text-center text-ir-teal text-sm font-semibold">
                              Submitting vote...
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Instructions */}
                <div className="border-t border-ir-navy border-opacity-10 pt-6">
                  <div className="bg-ir-teal-light border-l-4 border-ir-turquoise p-4 rounded-tile">
                    <p className="text-sm text-ir-teal">
                      <strong>How it works:</strong> Choose the backronym you think is most creative.
                      {isParticipant
                        ? ' The backronym with the most votes wins the prize pool!'
                        : ` If you pick the winner, you'll earn 20 IC (net +10 IC after the ${voteCost} IC voting fee).`}
                    </p>
                  </div>
                </div>

                {/* Cost Info */}
                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between text-sm">
                    <div>
                      <strong className="text-gray-700">Your Balance:</strong>{' '}
                      <InitCoinDisplay amount={player.wallet} />
                    </div>
                    {!isParticipant && (
                      <div>
                        <strong className="text-gray-700">Vote Cost:</strong>{' '}
                        <InitCoinDisplay amount={voteCost} />
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Back to Dashboard Button */}
            <button
              onClick={() => navigate('/dashboard')}
              disabled={isSubmitting}
              className="w-full mt-6 flex items-center justify-center gap-2 text-gray-600 hover:text-gray-800 disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span>Back to Dashboard</span>
            </button>
        </div>
      </div>
    </div>
  );
};

export default Voting;
