import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import { extractErrorMessage } from '../api/client';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { UpgradeGuestAccount } from '../components/UpgradeGuestAccount';
import { LoadingSpinner } from '../components/LoadingSpinner';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';

export const Dashboard: React.FC = () => {
  const { state, actions } = useGame();
  const { startTutorial, skipTutorial } = useTutorial();
  const navigate = useNavigate();
  const location = useLocation();

  const {
    player,
    roundAvailability,
  } = state;
  const { refreshDashboard, startVoteRound } = actions;

  const [isStartingRound, setIsStartingRound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showTutorialWelcome, setShowTutorialWelcome] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    refreshDashboard(controller.signal).finally(() => setLoading(false));
    return () => controller.abort();
  }, [refreshDashboard]);

  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    if (searchParams.get('startTutorial') === 'true') {
      setShowTutorialWelcome(true);
      searchParams.delete('startTutorial');
      const newSearch = searchParams.toString();
      navigate(`/dashboard${newSearch ? `?${newSearch}` : ''}`, { replace: true });
    }
  }, [location.search, navigate]);

  const handleStartVote = async () => {
    if (isStartingRound) return;
    setIsStartingRound(true);
    setError(null);

    try {
      const round = await startVoteRound();
      navigate('/game/vote', { state: { round } });
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to start a round right now.');
    } finally {
      setIsStartingRound(false);
    }
  };

  const handleStartTutorial = async () => {
    setShowTutorialWelcome(false);
    await startTutorial();
  };

  const handleSkipTutorial = async () => {
    setShowTutorialWelcome(false);
    await skipTutorial();
  };

  const freeCaptionsRemaining = roundAvailability?.free_captions_remaining;

  return (
    <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
      {showTutorialWelcome && (
        <TutorialWelcome
          onStart={handleStartTutorial}
          onSkip={handleSkipTutorial}
        />
      )}
      {player?.is_guest && <UpgradeGuestAccount className="mb-4" />}
      <div className="tile-card p-6 md:p-8 tutorial-dashboard">
        <div className="mb-6">
          <p className="text-sm text-quip-teal uppercase tracking-wide">Welcome back</p>
          <h1 className="text-3xl font-display font-bold text-quip-navy">MemeMint Arcade</h1>
        </div>

        {loading ? (
          <div className="py-10 flex justify-center">
            <LoadingSpinner isLoading message="Loading your dashboard..." />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="border-2 border-quip-navy rounded-tile p-4 bg-white">
                <p className="text-sm text-quip-teal">Wallet</p>
                <div className="text-2xl font-display font-bold text-quip-navy flex items-center gap-2">
                  <CurrencyDisplay amount={player?.wallet || 0} />
                </div>
              </div>
              <div className="border-2 border-quip-teal rounded-tile p-4 bg-white">
                <p className="text-sm text-quip-teal">Free captions left today</p>
                <p className="text-2xl font-display font-bold text-quip-navy">
                  {freeCaptionsRemaining ?? '—'}
                </p>
              </div>
            </div>

            {error && (
              <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            <div className="rounded-tile border-2 border-quip-orange bg-gradient-to-r from-quip-orange to-quip-orange-deep text-white p-8 text-center">
              <h2 className="text-2xl font-display font-bold mb-2">Browse Memes & Play</h2>
              <p className="text-lg mb-4">Start a vote round to see a fresh meme and pick your favorite caption.</p>
              <div className="flex items-center justify-center gap-2 mb-6 text-lg">
                <span>Entry cost:</span>
                <CurrencyDisplay amount={roundAvailability?.round_entry_cost ?? 5} iconClassName="w-5 h-5" textClassName="font-bold text-lg" />
              </div>
              <button
                onClick={handleStartVote}
                disabled={isStartingRound}
                className="bg-white text-quip-orange font-bold py-3 px-8 rounded-tile shadow-tile hover:shadow-tile-sm transition-colors disabled:opacity-70"
              >
                {isStartingRound ? 'Preparing your round...' : 'Start Game'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
