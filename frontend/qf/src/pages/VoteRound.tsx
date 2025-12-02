import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '@/api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { PhraseRecapCard } from '../components/PhraseRecapCard';
import { useTimer } from '@crowdcraft/hooks/useTimer.ts';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { VoteResponse, VoteState, PhrasesetDetails } from '@crowdcraft/api/types.ts';
import { voteRoundLogger } from '@crowdcraft/utils/logger.ts';
import { VoteRoundIcon } from '@crowdcraft/components/icons/RoundIcons.tsx';
import { HomeIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import { usePartyMode } from '../contexts/PartyModeContext';
import PartyRoundModal from '../components/party/PartyRoundModal';
import { usePartyNavigation } from '../hooks/usePartyNavigation';

export const VoteRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability } = state;
  const { refreshDashboard } = actions;
  const { state: partyState, actions: partyActions } = usePartyMode();
  const navigate = useNavigate();
  const { navigateHome, navigateToResults, isInPartyMode } = usePartyNavigation();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [voteResult, setVoteResult] = useState<VoteResponse | null>(null);
  const [headingMessage, setHeadingMessage] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [phrasesetDetails, setPhrasesetDetails] = useState<PhrasesetDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const roundData = activeRound?.round_type === 'vote' ? activeRound.state as VoteState : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  useEffect(() => {
    if (partyState.isPartyMode) {
      partyActions.setCurrentStep('vote');
    }
  }, [partyActions, partyState.isPartyMode]);

  const partyResultsPath = partyState.sessionId ? `/party/results/${partyState.sessionId}` : '/party/results';

  // Get dynamic values from config or use defaults
  const voteCost = roundAvailability?.vote_cost || 10;
  const votePayoutCorrect = roundAvailability?.vote_payout_correct || 20;
  const netGain = votePayoutCorrect - voteCost;

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      if (partyState.isPartyMode) {
        partyActions.endPartyMode();
        navigate(partyResultsPath);
      } else {
        navigate('/dashboard');
      }
    }
  }, [navigate, partyActions, partyResultsPath, partyState.isPartyMode, roundData?.status]);

  // Redirect if no active vote round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'vote') {
      // Don't start a new round if we're showing heading message or vote result
      if (headingMessage || voteResult) {
        return;
      }

      // Add a small delay to prevent race conditions during navigation
      const timeoutId = setTimeout(() => {
        // Redirect to dashboard instead of starting new rounds
        if (partyState.isPartyMode) {
          partyActions.endPartyMode();
          navigate(partyResultsPath);
        } else {
          navigate('/dashboard');
        }
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, headingMessage, navigate, partyActions, partyResultsPath, partyState.isPartyMode, voteResult]);

  const navigateAfterVote = useCallback(() => {
    navigateToResults();
  }, [navigateToResults]);

  const partyOverlay = partyState.isPartyMode && partyState.sessionId ? (
    <PartyRoundModal sessionId={partyState.sessionId} currentStep="vote" />
  ) : null;

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
    }, [roundData]);

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

      // Update party context if present
      if (result.party_context && partyState.isPartyMode) {
        partyActions.updateFromPartyContext(result.party_context);
        voteRoundLogger.debug('Updated party context after vote submission', {
          yourProgress: result.party_context.your_progress,
        });
      }

      const heading = result.correct ? getRandomMessage('voteCorrectHeading') : getRandomMessage('voteIncorrectHeading');
      setHeadingMessage(heading);
      const feedback = result.correct ? getRandomMessage('voteCorrect') : getRandomMessage('voteIncorrect');
      setFeedbackMessage(feedback);
      setVoteResult(result);
      voteRoundLogger.info('Vote submitted', {
        roundId: roundData.round_id,
        correct: result.correct,
      });

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
    voteRoundLogger.debug('Dismissing vote results');
    navigateAfterVote();
  };

  // Show vote result (check this first, before checking roundData)
  if (voteResult) {
    const voteCount = phrasesetDetails?.vote_count || 0;
    const votes = phrasesetDetails?.votes || [];
    const isFirstVoter = voteCount === 1;

    return (
      <>
        {partyOverlay}
        <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
          <div className="max-w-3xl w-full tile-card p-8 flip-enter">
          {/* Header with icon and result */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <VoteRoundIcon
                className={`w-32 h-32 ${voteResult.correct ? '' : 'opacity-60'}`}
                aria-hidden="true"
              />
            </div>

            {/* Large Check/X-mark indicator */}
            <div className="flex justify-center mb-4">
              <div className={`inline-flex items-center justify-center w-24 h-24 rounded-full border-4 ${voteResult.correct ? 'bg-ccl-turquoise border-ccl-turquoise text-white' : 'bg-ccl-orange border-ccl-orange text-white'} shadow-tile`}>
                <span className="text-7xl font-bold leading-none" style={{ marginTop: '-4px' }}>
                  {voteResult.correct ? '✓' : '✗'}
                </span>
              </div>
            </div>

            {/* Main result message */}
            <h2 className={`text-5xl font-display font-bold mb-6 success-message ${voteResult.correct ? 'text-ccl-turquoise' : 'text-ccl-orange'}`}>
              {headingMessage}
            </h2>

            {/* Payout/Cost info - PROMINENT */}
            <div className={`inline-flex items-center gap-2 px-6 py-4 rounded-tile mb-8 ${voteResult.payout > 0 ? 'bg-ccl-turquoise bg-opacity-20 border-2 border-ccl-turquoise' : 'bg-ccl-orange bg-opacity-10 border-2 border-ccl-orange'}`}>
              {voteResult.payout > 0 ? (
                <>
                  <span className="text-ccl-navy font-display font-bold text-xl">You earned:</span>
                  <CurrencyDisplay amount={voteResult.payout} iconClassName="w-7 h-7" textClassName="text-2xl font-bold text-ccl-turquoise" />
                </>
              ) : (
                <>
                  <span className="text-ccl-navy font-display font-bold text-xl">No flipcoins earned</span>
                </>
              )}
            </div>

            {/* Simple feedback message */}
            <p className="text-lg text-ccl-teal mb-6">
              {feedbackMessage}
            </p>
          </div>

          {/* Collapsible Details Section */}
          <div className="mb-6">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="w-full flex items-center justify-between p-4 bg-ccl-navy bg-opacity-5 hover:bg-opacity-10 border-2 border-ccl-navy rounded-tile transition-all mb-2"
            >
              <span className="font-display font-bold text-lg text-ccl-navy">
                View Details
              </span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className={`h-6 w-6 text-ccl-navy transition-transform ${showDetails ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Expandable content */}
            {showDetails && (
              <div className="space-y-4 slide-up-enter">
                {/* The Reveal - Show all phrases with attributions */}
                <div className="bg-ccl-navy bg-opacity-5 border-2 border-ccl-navy rounded-tile p-6">
                  <h3 className="font-display font-bold text-xl text-ccl-navy mb-4 text-center">
                    The Reveal
                  </h3>

                  {loadingDetails ? (
                    <div className="text-center py-6">
                      <LoadingSpinner isLoading={true} message="Loading details..." />
                    </div>
                  ) : phrasesetDetails ? (
                    <div className="space-y-3">
                      {/* Map through all three phrases and show their authors */}
                      {[
                        phrasesetDetails.original_phrase,
                        phrasesetDetails.copy_phrase_1,
                        phrasesetDetails.copy_phrase_2
                      ].filter((phrase): phrase is string => phrase !== null).map((phrase) => {
                        const isOriginal = phrase === voteResult.original_phrase;
                        const isYourChoice = phrase === voteResult.your_choice;
                        const contributor = phrasesetDetails.contributors.find(c => c.phrase === phrase);

                        return (
                          <PhraseRecapCard
                            key={phrase}
                            phrase={phrase}
                            isOriginal={isOriginal}
                            isYourChoice={isYourChoice}
                            isCorrectChoice={voteResult.correct}
                            contributor={contributor}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    // Fallback if phrasesetDetails isn't loaded yet
                    <div className="space-y-2">
                      <p className="text-lg text-ccl-navy mb-2">
                        The original phrase was: <strong className="text-ccl-turquoise">{voteResult.original_phrase}</strong>
                      </p>
                      <p className="text-lg text-ccl-teal">
                        You chose: <strong className={voteResult.correct ? 'text-ccl-turquoise' : 'text-ccl-orange'}>{voteResult.your_choice}</strong>
                      </p>
                    </div>
                  )}
                </div>

                {/* Vote information section */}
                {phrasesetDetails && (
                  <>
                    {/* First voter encouragement */}
                    {isFirstVoter && (
                      <div className="bg-ccl-orange bg-opacity-10 border-2 border-ccl-orange rounded-tile p-4 text-center">
                        <p className="text-ccl-navy font-display font-semibold mb-2">
                          You're the first to vote on this one!
                        </p>
                        <p className="text-ccl-teal text-sm mb-3">
                          Come back later to see how others voted. You can check in on this round anytime from Round Tracking.
                        </p>
                      </div>
                    )}

                    {/* Vote details for multiple voters */}
                    {!isFirstVoter && votes.length > 0 && (
                      <div className="bg-ccl-navy bg-opacity-5 border-2 border-ccl-navy rounded-tile p-4">
                        <h3 className="font-display font-bold text-lg text-ccl-navy mb-3 text-center">
                          Voting Results ({voteCount} vote{voteCount !== 1 ? 's' : ''} so far)
                        </h3>
                        <div className="space-y-2">
                          {votes.map((vote) => (
                            <div
                              key={vote.vote_id}
                              className={`flex items-center justify-between p-3 rounded-tile ${vote.correct ? 'bg-ccl-turquoise bg-opacity-10 border border-ccl-turquoise' : 'bg-ccl-orange bg-opacity-10 border border-ccl-orange'}`}
                            >
                              <div className="flex items-center gap-3">
                                <span className="font-semibold text-ccl-navy">
                                  {vote.voter_username}
                                </span>
                                <span className="text-sm text-ccl-teal">
                                  voted for: <strong>{vote.voted_phrase}</strong>
                                </span>
                              </div>
                              <span className={`text-sm font-semibold ${vote.correct ? 'text-ccl-turquoise' : 'text-ccl-orange'}`}>
                                {vote.correct ? '✓ Correct' : '✗ Incorrect'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Round Tracking Button - Only visible in dropdown */}
                    <div className="text-center pt-2">
                      <Link
                        to="/tracking"
                        className="inline-block bg-ccl-orange hover:bg-ccl-orange-deep text-white font-semibold py-3 px-6 rounded-tile transition-colors"
                      >
                        Go to Round Tracking →
                      </Link>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Back to Dashboard button - ALWAYS VISIBLE */}
          <div className="flex justify-center">
            <button
              onClick={handleDismiss}
              className="bg-ccl-turquoise hover:bg-ccl-teal text-white font-bold py-3 px-8 rounded-tile transition-all hover:shadow-tile-sm flex items-center gap-2"
            >
              <HomeIcon className="h-5 w-5" />
              <span>{isInPartyMode ? 'View Party Summary' : 'Back to Dashboard'}</span>
            </button>
          </div>
        </div>
      </div>
      </>
    );
  }

  // If no roundData and no vote result, show loading
  if (!roundData) {
    return (
      <>
        {partyOverlay}
        <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center">
          <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
        </div>
      </>
    );
  }

  return (
    <>
      {partyOverlay}
      <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-orange-deep flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <VoteRoundIcon className="w-8 h-8" aria-hidden="true" />
            <h1 className="text-3xl font-display font-bold text-ccl-navy">Guess the Original</h1>
          </div>
          <p className="text-ccl-teal">One is the original answer. Two are fakes. Tap the one you think came first.</p>
        </div>

        {/* Timer */}
        <div className="flex justify-center mb-6">
          <Timer expiresAt={roundData.expires_at} />
        </div>

        {/* Prompt */}
        <div className="bg-ccl-orange bg-opacity-5 border-2 border-ccl-orange rounded-tile p-6 mb-6">
          <p className="text-sm text-ccl-teal mb-2 text-center font-medium">Prompt:</p>
          <p className="text-2xl text-center font-display font-semibold text-ccl-orange-deep">
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
          <p className="text-center text-ccl-navy font-display font-semibold mb-4 text-lg">
            Which phrase was written first?
          </p>
          {roundData.phrases.map((phrase, idx) => (
            <button
              key={phrase}
              onClick={() => handleVote(phrase)}
              disabled={isExpired || isSubmitting}
              className="w-full bg-ccl-orange hover:bg-ccl-orange-deep disabled:bg-gray-400 text-white font-bold py-4 px-6 rounded-tile transition-all hover:shadow-tile-sm text-xl shuffle-enter"
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              {phrase}
            </button>
          ))}
        </div>

        {isExpired && (
          <div className="text-center text-ccl-orange-deep font-semibold">
            Time's up! Refund of <CurrencyDisplay amount={voteCost - (roundAvailability?.abandoned_penalty || 5)} iconClassName="w-4 h-4" textClassName="font-semibold" /> applied ({roundAvailability?.abandoned_penalty || 5} FC penalty)
          </div>
        )}

        {/* Home Button */}
        <button
          onClick={navigateHome}
          disabled={isSubmitting}
          className="w-full mt-4 flex items-center justify-center gap-2 text-ccl-teal hover:text-ccl-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
          title={isSubmitting ? "Please wait for submission to complete" : isInPartyMode ? "Leave Party Mode" : "Back to Dashboard"}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>{isInPartyMode ? 'Exit Party Mode' : 'Back to Dashboard'}</span>
        </button>

        {/* Info */}
        <div className="mt-6 p-4 bg-ccl-orange bg-opacity-5 rounded-tile">
          <p className="text-sm text-ccl-teal inline-flex items-center flex-wrap gap-1">
            <strong className="text-ccl-navy">Cost:</strong> <CurrencyDisplay amount={voteCost} iconClassName="w-3 h-3" textClassName="text-sm" /> • <strong className="text-ccl-navy">Correct answer:</strong> +<CurrencyDisplay amount={votePayoutCorrect} iconClassName="w-3 h-3" textClassName="text-sm" /> (+<CurrencyDisplay amount={netGain} iconClassName="w-3 h-3" textClassName="text-sm" /> net)
          </p>
        </div>
      </div>
    </div>
    </>
  );
};

export default VoteRound;
