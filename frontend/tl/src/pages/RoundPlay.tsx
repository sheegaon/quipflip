import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '@/api/client';
import type { StartRoundResponse } from '@/api/types';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { GuessInput } from '../components/GuessInput';
import { CoverageBar } from '../components/CoverageBar';
import { StrikeIndicator } from '../components/StrikeIndicator';
import { MatchFeedback } from '../components/MatchFeedback';

interface RoundPlayLocationState {
  round?: StartRoundResponse;
}

interface Guess {
  text: string;
  wasMatch: boolean;
  causedStrike: boolean;
  timestamp: number;
}

export const RoundPlay: React.FC = () => {
  const navigate = useNavigate();
  const { state: gameState } = useGame();
  const { player } = gameState;
  const locationState = (useLocation().state as RoundPlayLocationState) || {};
  const initialRound = locationState.round;

  // State
  const [round] = useState<StartRoundResponse | null>(initialRound || null);
  const [guessText, setGuessText] = useState('');
  const [guesses, setGuesses] = useState<Guess[]>([]);
  const [strikes, setStrikes] = useState(0);
  const [coverage, setCoverage] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAbandoning, setIsAbandoning] = useState(false);
  const [roundEnded, setRoundEnded] = useState(false);
  const [finalResult, setFinalResult] = useState<any>(null);

  // Check if round should end (3 strikes)
  useEffect(() => {
    if (strikes >= 3 && !roundEnded) {
      finalizRound();
    }
  }, [strikes, roundEnded]);

  const handleSubmitGuess = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!guessText.trim() || !round || isSubmitting || roundEnded) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiClient.submitGuess(round.round_id, guessText.trim());

      // Add guess to history
      const newGuess: Guess = {
        text: guessText.trim(),
        wasMatch: response.was_match,
        causedStrike: response.new_strikes > strikes,
        timestamp: Date.now(),
      };

      setGuesses(prev => [...prev, newGuess]);
      setStrikes(response.new_strikes);
      setCoverage(response.current_coverage);
      setGuessText('');

      // Speak feedback
      speakFeedback(newGuess);

      // Check if round ended
      if (response.round_status === 'completed') {
        await finalizRound();
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

  const speakFeedback = (guess: Guess) => {
    const message = guess.wasMatch
      ? `Match! You matched ${guess.text}`
      : guess.causedStrike
      ? `No match. Strike!`
      : 'No match.';

    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.rate = 1.2;
      speechSynthesis.speak(utterance);
    }
  };

  const finalizRound = async () => {
    if (!round) return;

    try {
      setRoundEnded(true);
      const details = await apiClient.getRoundDetails(round.round_id);

      const result = {
        roundId: round.round_id,
        promptText: round.prompt_text,
        finalCoverage: details.final_coverage || 0,
        grossPayout: details.gross_payout || 0,
        strikeCount: strikes,
        matchedClusters: details.matched_clusters?.length || 0,
        totalClusters: 0, // Would need snapshot data
      };

      // Calculate payout (would come from backend in production)
      const coveragePercent = details.final_coverage || 0;
      const grossPayout = Math.round(300 * Math.pow(coveragePercent, 1.5));
      const walletAward = coveragePercent <= 0.33
        ? grossPayout
        : Math.max(100, grossPayout - Math.floor((grossPayout - 100) * 0.3));

      setFinalResult({
        ...result,
        grossPayout,
        walletAward,
        vaultAward: grossPayout - walletAward,
      });
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to finalize round');
    }
  };

  const handleAbandonRound = async () => {
    if (!round || !confirm('Are you sure? You\'ll get a 95 coin refund and lose this round.')) {
      return;
    }

    setIsAbandoning(true);
    setError(null);

    try {
      await apiClient.abandonRound(round.round_id);
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
      <div className="bg-gradient-to-r from-ccl-navy to-ccl-navy-deep text-white p-6 md:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl md:text-4xl font-display font-bold mb-4 text-center">
            {round.prompt_text}
          </h1>
          <p className="text-center text-ccl-cream text-sm">
            {round.snapshot_answer_count} answers · {round.snapshot_total_weight.toFixed(0)} total weight
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8">
        <div className="max-w-2xl w-full space-y-8">
          {/* Coverage Bar */}
          <CoverageBar coverage={coverage * 100} />

          {/* Strike Indicator */}
          <StrikeIndicator strikes={strikes} />

          {/* Recent Guesses */}
          <MatchFeedback guesses={guesses} />

          {/* Guess Input */}
          <GuessInput
            value={guessText}
            onChange={setGuessText}
            onSubmit={handleSubmitGuess}
            isSubmitting={isSubmitting}
            error={error}
            autoFocus={true}
          />

          {/* Stats Footer */}
          <div className="grid grid-cols-3 gap-4 text-center text-sm">
            <div className="tile-card p-4">
              <p className="text-ccl-teal">Guesses</p>
              <p className="text-2xl font-display font-bold text-ccl-navy">{guesses.length}</p>
            </div>
            <div className="tile-card p-4">
              <p className="text-ccl-teal">Wallet</p>
              <p className="text-xl font-display font-bold text-ccl-navy">
                <CurrencyDisplay amount={player?.tl_wallet || 0} />
              </p>
            </div>
            <div className="tile-card p-4">
              <p className="text-ccl-teal">Vault</p>
              <p className="text-xl font-display font-bold text-ccl-navy">
                <CurrencyDisplay amount={player?.tl_vault || 0} />
              </p>
            </div>
          </div>

          {/* Abandon Button */}
          <button
            onClick={handleAbandonRound}
            disabled={isAbandoning}
            className="w-full py-2 text-red-600 border-2 border-red-400 rounded-tile hover:bg-red-50 disabled:opacity-50 font-semibold text-sm"
          >
            {isAbandoning ? 'Abandoning...' : 'Abandon Round (95 coins refund)'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoundPlay;
