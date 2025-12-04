import React, { useEffect, useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import type { TLStartRoundResponse } from '@crowdcraft/api/types.ts';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { GuessInput } from '../components/GuessInput';
import { CoverageBar } from '../components/CoverageBar';
import { StrikeIndicator } from '../components/StrikeIndicator';
import { MatchFeedback } from '../components/MatchFeedback';
import { Tooltip } from '../components/Tooltip';

interface RoundPlayLocationState {
  round?: TLStartRoundResponse;
}

interface FinalResult {
  roundId: string;
  promptText: string;
  finalCoverage: number;
  grossPayout: number;
  strikeCount: number;
  matchedClusters: number;
  totalClusters: number;
  walletAward: number;
  vaultAward: number;
}

interface Guess {
  text: string;
  wasMatch: boolean;
  causedStrike: boolean;
  timestamp: number;
}

const normalizeGuessText = (text: string) => text.trim().replace(/\s+/g, ' ');

const getWords = (phrase: string) => phrase.match(/[A-Za-z']+/g) || [];

const validateGuessLocally = (guess: string): string | null => {
  const normalized = normalizeGuessText(guess);

  if (!normalized) {
    return 'Enter a guess to submit';
  }

  if (normalized.length < 4 || normalized.length > 100) {
    return 'Use 4-100 characters';
  }

  if (!/^[A-Za-z\s']+$/.test(normalized)) {
    return 'Use letters, spaces, and apostrophes only';
  }

  const words = getWords(normalized);

  if (words.length < 2 || words.length > 5) {
    return 'Enter 2-5 words';
  }

  return null;
};

const levenshteinDistance = (a: string, b: string): number => {
  if (a === b) return 0;
  const matrix = Array.from({ length: a.length + 1 }, (_, i) =>
    Array.from({ length: b.length + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)),
  );

  for (let i = 1; i <= a.length; i += 1) {
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost,
      );
    }
  }

  return matrix[a.length][b.length];
};

const similarityScore = (a: string, b: string): number => {
  if (!a || !b) return 0;
  const distance = levenshteinDistance(a.toLowerCase(), b.toLowerCase());
  const maxLength = Math.max(a.length, b.length);
  if (maxLength === 0) return 1;
  return 1 - distance / maxLength;
};

export const RoundPlay: React.FC = () => {
  const navigate = useNavigate();
  const locationState = (useLocation().state as RoundPlayLocationState) || {};
  const initialRound = locationState.round;

  // State
  const [round] = useState<TLStartRoundResponse | null>(initialRound || null);
  const [guessText, setGuessText] = useState('');
  const [guesses, setGuesses] = useState<Guess[]>([]);
  const [strikes, setStrikes] = useState(0);
  const [coverage, setCoverage] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAbandoning, setIsAbandoning] = useState(false);
  const [roundEnded, setRoundEnded] = useState(false);
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);

  const handleSubmitGuess = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!guessText.trim() || !round || isSubmitting || roundEnded) {
      return;
    }

    const normalizedGuess = normalizeGuessText(guessText);
    const validationError = validateGuessLocally(normalizedGuess);

    if (validationError) {
      setError(validationError);
      return;
    }

    const similarityHit = guesses.some((priorGuess) =>
      similarityScore(normalizedGuess, priorGuess.text) >= 0.8,
    );

    if (similarityHit) {
      setError('Too similar to your previous guess. Try a new idea.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiClient.tlSubmitGuess(round.round_id, normalizedGuess);

      // Add guess to history
      const newGuess: Guess = {
        text: normalizedGuess,
        wasMatch: response.was_match,
        causedStrike: response.new_strikes > strikes,
        timestamp: Date.now(),
      };

      setGuesses(prev => [...prev, newGuess]);
      setStrikes(response.new_strikes);
      setCoverage(response.current_coverage);
      setGuessText('');

      // Check if round ended
      if (response.round_status === 'completed') {
        await finalizeRound();
      }
    } catch (err) {
      const msg = extractErrorMessage(err);
      if (msg.includes('insufficient_balance') || msg.includes('round_not_found')) {
        navigate('/dashboard');
      } else {
        setError(msg || 'Failed to submit guess. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const finalizeRound = useCallback(async () => {
    if (!round) return;

    try {
      setRoundEnded(true);
      const details = await apiClient.tlGetRoundDetails(round.round_id);

      const result = {
        roundId: round.round_id,
        promptText: round.prompt_text,
        finalCoverage: details.final_coverage || 0,
        grossPayout: details.gross_payout || 0,
        strikeCount: strikes,
        matchedClusters: details.matched_clusters?.length || 0,
        totalClusters: details.snapshot_answer_count || 0,
      };

      setFinalResult({
        ...result,
        grossPayout: result.grossPayout,
        walletAward: details.wallet_award ?? result.grossPayout,
        vaultAward: details.vault_award ?? 0,
      });
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to finalize round');
    }
  }, [round, strikes]);

  useEffect(() => {
    if (strikes >= 3 && !roundEnded) {
      finalizeRound();
    }
  }, [strikes, roundEnded, finalizeRound]);

  const handleAbandonRound = async () => {
    if (!round) return;

    setIsAbandoning(true);
    setError(null);

    try {
      await apiClient.tlAbandonRound(round.round_id);
      navigate('/dashboard');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to abandon round');
      setIsAbandoning(false);
    }
  };

  if (!round) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner isLoading message="Loading round..." />
      </div>
    );
  }

  if (roundEnded && finalResult) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
        <div className="max-w-2xl w-full text-center">
          <div className="mb-8">
            <h1 className="text-5xl font-display font-bold text-ccl-orange mb-4">
              Round Complete!
            </h1>
            <p className="text-2xl font-display text-ccl-navy">
              {Math.round(finalResult.finalCoverage * 100)}% Coverage
            </p>
          </div>

          <button
            onClick={() =>
              navigate('/results', {
                state: {
                  roundId: finalResult.roundId,
                  promptText: finalResult.promptText,
                  finalCoverage: finalResult.finalCoverage,
                  grossPayout: finalResult.grossPayout,
                  walletAward: finalResult.walletAward,
                  vaultAward: finalResult.vaultAward,
                  strikeCount: finalResult.strikeCount,
                  matchedClusters: finalResult.matchedClusters,
                },
              })
            }
            className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-4 px-8 rounded-tile text-lg"
          >
            View Results
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern flex flex-col">
      {/* Header */}
      <header className="bg-ccl-navy text-white p-6 md:p-8 shadow-lg">
        <div className="max-w-4xl mx-auto">
          <div className="bg-ccl-teal/30 border border-ccl-teal/30 rounded-2xl p-6 md:p-8 shadow-lg backdrop-blur-sm">
            <h1 className="text-3xl md:text-4xl font-display font-bold mb-4 text-center" role="heading" aria-level={1}>
              {round.prompt_text}
            </h1>
            <p className="text-center text-ccl-cream text-sm" aria-label={`Round has ${round.snapshot_answer_count} answers with ${round.snapshot_total_weight.toFixed(0)} total weight`}>
              {round.snapshot_answer_count} answers · {round.snapshot_total_weight.toFixed(0)} total weight
            </p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8">
        <div className="max-w-2xl w-full space-y-8">
          <div className="flex flex-col md:flex-row gap-4 md:items-stretch">
            {/* Coverage Bar */}
            <Tooltip content="Coverage % shows how many of the crowd's answers you've matched. Higher coverage = bigger payout!">
              <div className="flex-1 md:flex-[1.25]">
                <CoverageBar coverage={coverage * 100} />
              </div>
            </Tooltip>

            {/* Strike Indicator */}
            <div className="flex flex-row flex-wrap gap-2 sm:gap-3 md:gap-4 md:w-[380px] items-stretch">
              <Tooltip content="Get 3 strikes and your round ends. Try common, obvious answers to avoid wrong guesses.">
                <div className="flex-1 min-w-[160px]">
                  <StrikeIndicator strikes={strikes} />
                </div>
              </Tooltip>

              <div className="tile-card p-4 sm:p-5 flex-1 min-w-[140px] flex flex-col justify-center items-center text-center">
                <p className="text-ccl-teal text-sm" id="guess-count-label">Guesses</p>
                <p className="text-2xl sm:text-3xl font-display font-bold text-ccl-navy" aria-labelledby="guess-count-label">
                  {guesses.length}
                </p>
              </div>
            </div>
          </div>

          {/* Recent Guesses */}
          <MatchFeedback guesses={guesses} />

          {/* Guess Input */}
          <div className="space-y-3">
            <GuessInput
              value={guessText}
              onChange={setGuessText}
              onSubmit={handleSubmitGuess}
              isSubmitting={isSubmitting}
              error={error}
              autoFocus={true}
            />
          </div>

          {/* Abandon Button */}
          <button
            onClick={handleAbandonRound}
            disabled={isAbandoning}
            className="w-full py-3 bg-ccl-orange text-white rounded-tile shadow-md hover:bg-ccl-orange-deep disabled:opacity-60 font-semibold text-sm transition-colors"
            aria-label="Abandon round - forfeit this round and get 95 coins refunded"
            title="Abandon this round and receive a 95 coin refund"
          >
            {isAbandoning ? 'Abandoning...' : 'Abandon Round (95 coins refund)'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoundPlay;
