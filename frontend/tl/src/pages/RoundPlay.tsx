import React, { useEffect, useState , useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import type { TLStartRoundResponse } from '@crowdcraft/api/types.ts';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
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

export const RoundPlay: React.FC = () => {
  const navigate = useNavigate();
  const { state: gameState } = useGame();
  const { player } = gameState;
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

  // Check if round should end (3 strikes)
  useEffect(() => {
    if (strikes >= 3 && !roundEnded) {
      finalizeRound();
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
      const response = await apiClient.tlSubmitGuess(round.round_id, guessText.trim());

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
  }, [round, strikes, navigate]);

  useEffect(() => {
  if (strikes >= 3 && !roundEnded) {
    finalizeRound();
  }
}, [strikes, roundEnded, finalizeRound]);

  const handleAbandonRound = async () => {
    if (!round || !confirm('Are you sure? You\'ll get a 95 coin refund and lose this round.')) {
      return;
    }

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
      <header className="bg-gradient-to-r from-ccl-navy to-ccl-navy-deep text-white p-6 md:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl md:text-4xl font-display font-bold mb-4 text-center" role="heading" aria-level={1}>
            {round.prompt_text}
          </h1>
          <p className="text-center text-ccl-cream text-sm" aria-label={`Round has ${round.snapshot_answer_count} answers with ${round.snapshot_total_weight.toFixed(0)} total weight`}>
            {round.snapshot_answer_count} answers · {round.snapshot_total_weight.toFixed(0)} total weight
          </p>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8">
        <div className="max-w-2xl w-full space-y-8">
          {/* Coverage Bar */}
          <Tooltip content="Coverage % shows how many of the crowd's answers you've matched. Higher coverage = bigger payout!">
            <div>
              <CoverageBar coverage={coverage * 100} />
            </div>
          </Tooltip>

          {/* Strike Indicator */}
          <Tooltip content="Get 3 strikes and your round ends. Try common, obvious answers to avoid wrong guesses.">
            <div>
              <StrikeIndicator strikes={strikes} />
            </div>
          </Tooltip>

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
          <section className="grid grid-cols-3 gap-4 text-center text-sm" aria-label="Game statistics">
            <div className="tile-card p-4">
              <p className="text-ccl-teal" id="guess-count-label">Guesses</p>
              <p className="text-2xl font-display font-bold text-ccl-navy" aria-labelledby="guess-count-label">
                {guesses.length}
              </p>
            </div>
            <div className="tile-card p-4">
              <p className="text-ccl-teal" id="wallet-label">Wallet</p>
              <p className="text-xl font-display font-bold text-ccl-navy" aria-labelledby="wallet-label">
                <CurrencyDisplay amount={player?.tl_wallet || 0} />
              </p>
            </div>
            <div className="tile-card p-4">
              <p className="text-ccl-teal" id="vault-label">Vault</p>
              <p className="text-xl font-display font-bold text-ccl-navy" aria-labelledby="vault-label">
                <CurrencyDisplay amount={player?.tl_vault || 0} />
              </p>
            </div>
          </section>

          {/* Abandon Button */}
          <button
            onClick={handleAbandonRound}
            disabled={isAbandoning}
            className="w-full py-2 text-red-600 border-2 border-red-400 rounded-tile hover:bg-red-50 disabled:opacity-50 font-semibold text-sm"
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
