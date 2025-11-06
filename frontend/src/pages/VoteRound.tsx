import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { VoteResponse, VoteState, PhrasesetDetails } from '../api/types';
import { voteRoundLogger } from '../utils/logger';

export const VoteRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability } = state;
  const { refreshDashboard } = actions;
  const { currentStep, completeTutorial } = useTutorial();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [voteResult, setVoteResult] = useState<VoteResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [phrasesetDetails, setPhrasesetDetails] = useState<PhrasesetDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const roundData = activeRound?.round_type === 'vote' ? activeRound.state as VoteState : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Get dynamic values from config or use defaults
  const voteCost = roundAvailability?.vote_cost || 10;
  const votePayoutCorrect = roundAvailability?.vote_payout_correct || 20;
  const netGain = votePayoutCorrect - voteCost;

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      navigate('/dashboard');
    }
  }, [roundData?.status, navigate]);

  // Redirect if no active vote round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'vote') {
      // Don't start a new round if we're showing success message or vote result
      if (successMessage || voteResult) {
        return;
      }

      // Add a small delay to prevent race conditions during navigation
      const timeoutId = setTimeout(() => {
        // Redirect to dashboard instead of starting new rounds
        if (currentStep === 'vote_round') {
          completeTutorial();
        }
        navigate('/dashboard');
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, navigate, successMessage, voteResult, currentStep, completeTutorial]);

  useEffect(() => {
    if (!roundData) {
      voteRoundLogger.debug('Vote round page mounted without active round');
    } else {
      voteRoundLogger.debug('Vote round page mounted', {
        roundId: roundData.round_id,
        expiresAt: roundData.expires_at,
        status: roundData.status,
        prompt: roundData.prompt_text,
      });
    }
  }, [roundData?.round_id, roundData?.expires_at, roundData?.status, roundData?.prompt_text]);

  const handleVote = async (phrase: string) => {
    if (!roundData || isSubmitting) return;

    try {
      setIsSubmitting(true);
      setError(null);
      voteRoundLogger.debug('Submitting vote', {
        roundId: roundData.round_id,
        phrasesetId: roundData.phraseset_id,
        choice: phrase,
      });
      const result = await apiClient.submitVote(roundData.phraseset_id, phrase);

      const message = result.correct ? getRandomMessage('voteSubmitted') : null;
      setSuccessMessage(message);
      setVoteResult(result);
      voteRoundLogger.info('Vote submitted', {
        roundId: roundData.round_id,
        correct: result.correct,
      });

      if (currentStep === 'vote_round') {
        completeTutorial();
      }

      // Refresh dashboard to clear the active round state
      try {
        voteRoundLogger.debug('Refreshing dashboard after vote submission');
        await refreshDashboard();
        voteRoundLogger.debug('Dashboard refreshed successfully after vote');
      } catch (refreshErr) {
        voteRoundLogger.warn('Failed to refresh dashboard after vote:', refreshErr);
      }

      // Fetch phraseset details to show vote information
      try {
        setLoadingDetails(true);
        const details = await apiClient.getPhrasesetDetails(roundData.phraseset_id);
        setPhrasesetDetails(details);
      } catch (detailsErr) {
        voteRoundLogger.warn('Failed to fetch phraseset details:', detailsErr);
      } finally {
        setLoadingDetails(false);
      }
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to submit your vote. The round may have expired or someone else may have already voted.';
      voteRoundLogger.error('Failed to submit vote', err);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = () => {
    voteRoundLogger.debug('Dismissing vote results, navigating to dashboard');
    navigate('/dashboard');
  };

  // Show vote result (check this first, before checking roundData)
  if (voteResult) {
    const successMsg = voteResult.correct
      ? (successMessage || 'Correct!')
      : 'Better luck next time!';

    const voteCount = phrasesetDetails?.vote_count || 0;
    const votes = phrasesetDetails?.votes || [];
    const isFirstVoter = voteCount === 1;

    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="max-w-3xl w-full tile-card p-8 flip-enter">
          {/* Header with icon and result */}
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <img src="/icon_vote.svg" alt="" className="w-24 h-24" />
            </div>
            <h2 className={`text-3xl font-display font-bold mb-4 success-message ${voteResult.correct ? 'text-quip-turquoise' : 'text-quip-orange'}`}>
              {voteResult.correct ? successMsg : 'Incorrect'}
            </h2>
            {/* Enhanced Recap Card - Show all phrases with attributions */}
            <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 mb-4">
              <h3 className="font-display font-bold text-xl text-quip-navy mb-4 text-center">
                The Reveal
              </h3>

              {phrasesetDetails ? (
                <div className="space-y-3">
                  {/* Map through all three phrases and show their authors */}
                  {[
                    phrasesetDetails.original_phrase,
                    phrasesetDetails.copy_phrase_1,
                    phrasesetDetails.copy_phrase_2
                  ].filter(Boolean).map((phrase) => {
                    const isOriginal = phrase === voteResult.original_phrase;
                    const isYourChoice = phrase === voteResult.your_choice;
                    const contributor = phrasesetDetails.contributors.find(c => c.phrase === phrase);

                    // Determine styling based on whether it's original and/or player's choice
                    let borderColor = 'border-quip-teal';
                    let bgColor = 'bg-white';
                    let labelColor = 'text-quip-teal';

                    if (isOriginal) {
                      borderColor = 'border-quip-turquoise';
                      bgColor = 'bg-quip-turquoise bg-opacity-5';
                    }

                    return (
                      <div
                        key={phrase}
                        className={`relative ${bgColor} border-2 ${borderColor} rounded-tile p-4 transition-all`}
                      >
                        {/* Phrase text */}
                        <p className="text-lg font-semibold text-quip-navy mb-2">
                          "{phrase}"
                        </p>

                        {/* Author and badges */}
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-quip-teal">
                              Written by:
                            </span>
                            <span className={`text-sm font-semibold ${contributor?.is_you ? 'text-quip-orange' : 'text-quip-navy'}`}>
                              {contributor?.pseudonym || 'Unknown'}
                              {contributor?.is_you && ' (you)'}
                            </span>
                          </div>

                          {/* Badges */}
                          <div className="flex items-center gap-2">
                            {isOriginal && (
                              <span className="inline-flex items-center gap-1 px-3 py-1 bg-quip-turquoise text-white text-sm font-bold rounded-tile">
                                ⭐ Original
                              </span>
                            )}
                            {isYourChoice && (
                              <span className={`inline-flex items-center gap-1 px-3 py-1 ${voteResult.correct ? 'bg-quip-turquoise' : 'bg-quip-orange'} text-white text-sm font-bold rounded-tile`}>
                                {voteResult.correct ? '✓' : '✗'} Your Choice
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                // Fallback if phrasesetDetails isn't loaded yet
                <div className="space-y-2">
                  <p className="text-lg text-quip-navy mb-2">
                    The original phrase was: <strong className="text-quip-turquoise">{voteResult.original_phrase}</strong>
                  </p>
                  <p className="text-lg text-quip-teal">
                    You chose: <strong className={voteResult.correct ? 'text-quip-turquoise' : 'text-quip-orange'}>{voteResult.your_choice}</strong>
                  </p>
                </div>
              )}
            </div>

            {/* Payout info */}
            {voteResult.payout > 0 && (
              <div className="inline-flex items-center gap-2 bg-quip-turquoise bg-opacity-20 px-4 py-2 rounded-tile mb-4">
                <span className="text-quip-navy font-semibold">You earned:</span>
                <CurrencyDisplay amount={voteResult.payout} iconClassName="w-5 h-5" textClassName="text-lg font-bold text-quip-turquoise" />
              </div>
            )}
          </div>

          {/* Vote information section */}
          {loadingDetails ? (
            <div className="text-center py-6">
              <LoadingSpinner isLoading={true} message="Loading vote details..." />
            </div>
          ) : phrasesetDetails ? (
            <div className="space-y-4 mb-6">
              {/* First voter encouragement */}
              {isFirstVoter && (
                <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 text-center">
                  <p className="text-quip-navy font-display font-semibold mb-2">
                    🎉 You're the first to vote on this one!
                  </p>
                  <p className="text-quip-teal text-sm mb-3">
                    Come back later to see how others voted. You can check in on this round anytime from Round Tracking.
                  </p>
                  <Link
                    to="/tracking"
                    className="inline-block bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold py-2 px-4 rounded-tile transition-colors"
                  >
                    Go to Round Tracking →
                  </Link>
                </div>
              )}

              {/* Vote details for multiple voters */}
              {!isFirstVoter && votes.length > 0 && (
                <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-4">
                  <h3 className="font-display font-bold text-lg text-quip-navy mb-3 text-center">
                    Voting Results ({voteCount} vote{voteCount !== 1 ? 's' : ''} so far)
                  </h3>
                  <div className="space-y-2">
                    {votes.map((vote) => (
                      <div
                        key={vote.vote_id}
                        className={`flex items-center justify-between p-3 rounded-tile ${vote.correct ? 'bg-quip-turquoise bg-opacity-10 border border-quip-turquoise' : 'bg-quip-orange bg-opacity-10 border border-quip-orange'}`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-quip-navy">
                            {vote.voter_pseudonym}
                          </span>
                          <span className="text-sm text-quip-teal">
                            voted for: <strong>{vote.voted_phrase}</strong>
                          </span>
                        </div>
                        <span className={`text-sm font-semibold ${vote.correct ? 'text-quip-turquoise' : 'text-quip-orange'}`}>
                          {vote.correct ? '✓ Correct' : '✗ Incorrect'}
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-quip-teal text-center mt-3">
                    Track this round and see updates in <Link to="/tracking" className="text-quip-turquoise hover:underline font-semibold">Round Tracking</Link>
                  </p>
                </div>
              )}
            </div>
          ) : null}

          {/* Dismiss button */}
          <div className="flex justify-center">
            <button
              onClick={handleDismiss}
              className="bg-quip-turquoise hover:bg-quip-teal text-white font-bold py-3 px-8 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  // If no roundData and no vote result, show loading
  if (!roundData) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-orange-deep flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_vote.svg" alt="" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Vote Round</h1>
          </div>
          <p className="text-quip-teal">Identify the original phrase</p>
        </div>

        {/* Timer */}
        <div className="flex justify-center mb-6">
          <Timer expiresAt={roundData.expires_at} />
        </div>

        {/* Prompt */}
        <div className="bg-quip-orange bg-opacity-5 border-2 border-quip-orange rounded-tile p-6 mb-6">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Prompt:</p>
          <p className="text-2xl text-center font-display font-semibold text-quip-orange-deep">
            {roundData.prompt_text}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Phrase Choices */}
        <div className="tutorial-vote-options space-y-4 mb-6">
          <p className="text-center text-quip-navy font-display font-semibold mb-4 text-lg">
            Which phrase is the original?
          </p>
          {roundData.phrases.map((phrase, idx) => (
            <button
              key={phrase}
              onClick={() => handleVote(phrase)}
              disabled={isExpired || isSubmitting}
              className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-400 text-white font-bold py-4 px-6 rounded-tile transition-all hover:shadow-tile-sm text-xl shuffle-enter"
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              {phrase}
            </button>
          ))}
        </div>

        {isExpired && (
          <div className="text-center text-quip-orange-deep font-semibold">
            Time's up! Refund of <CurrencyDisplay amount={voteCost - (roundAvailability?.abandoned_penalty || 5)} iconClassName="w-4 h-4" textClassName="font-semibold" /> applied ({roundAvailability?.abandoned_penalty || 5} FC penalty)
          </div>
        )}

        {/* Home Button */}
        <button
          onClick={() => navigate('/dashboard')}
          disabled={isSubmitting}
          className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
          title={isSubmitting ? "Please wait for submission to complete" : "Back to Dashboard"}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>Back to Dashboard</span>
        </button>

        {/* Info */}
        <div className="mt-6 p-4 bg-quip-orange bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal inline-flex items-center flex-wrap gap-1">
            <strong className="text-quip-navy">Cost:</strong> <CurrencyDisplay amount={voteCost} iconClassName="w-3 h-3" textClassName="text-sm" /> • <strong className="text-quip-navy">Correct answer:</strong> +<CurrencyDisplay amount={votePayoutCorrect} iconClassName="w-3 h-3" textClassName="text-sm" /> (+<CurrencyDisplay amount={netGain} iconClassName="w-3 h-3" textClassName="text-sm" /> net)
          </p>
        </div>
      </div>
    </div>
  );
};

export default VoteRound;
