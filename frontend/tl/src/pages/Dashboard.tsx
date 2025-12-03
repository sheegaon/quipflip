import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { UpgradeGuestAccount } from '../components/UpgradeGuestAccount';
import { LoadingSpinner } from '../components/LoadingSpinner';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';
import { TrophyIcon } from '@crowdcraft/components/icons/EngagementIcons';

export const Dashboard: React.FC = () => {
  const { state, actions } = useGame();
  const {
    actions: { startTutorial, skipTutorial },
  } = useTutorial();
  const navigate = useNavigate();
  const location = useLocation();

  const { player } = state;
  const { refreshDashboard } = actions;

  const [isStartingRound, setIsStartingRound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showTutorialWelcome, setShowTutorialWelcome] = useState(false);
  const [roundAvailability, setRoundAvailability] = useState<any>(null);

  // Load dashboard and round availability
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    Promise.all([
      refreshDashboard(controller.signal),
      apiClient.tlCheckRoundAvailability(controller.signal).then(av => setRoundAvailability(av)).catch(() => ({}))
    ]).finally(() => setLoading(false));

    return () => controller.abort();
  }, [refreshDashboard]);

  // Check for tutorial start query param
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    if (searchParams.get('startTutorial') === 'true') {
      setShowTutorialWelcome(true);
      searchParams.delete('startTutorial');
      const newSearch = searchParams.toString();
      navigate(`/dashboard${newSearch ? `?${newSearch}` : ''}`, { replace: true });
    }
  }, [location.search, navigate]);

  const handleStartRound = async () => {
    if (isStartingRound) return;
    setIsStartingRound(true);
    setError(null);

    try {
      const round = await apiClient.tlStartRound();
      navigate('/play', { state: { round } });
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

  const entryCost = roundAvailability?.entry_cost ?? 100;
  const canStartRound = roundAvailability?.can_start_round ?? false;
  const errorReason = roundAvailability?.error_message;

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
          <h1 className="text-3xl font-display font-bold text-ccl-navy">ThinkLink</h1>
          <p className="text-ccl-teal mt-2 text-lg">Guess what others are thinking</p>
        </div>

        {loading ? (
          <div className="py-10 flex justify-center">
            <LoadingSpinner isLoading message="Loading your dashboard..." />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="border-2 border-ccl-navy rounded-tile p-4 bg-white">
                <p className="text-sm text-ccl-teal uppercase tracking-wide">Wallet</p>
                <div className="text-2xl font-display font-bold text-ccl-navy flex items-center gap-2">
                  <CurrencyDisplay amount={player?.tl_wallet || 0} />
                </div>
              </div>
              <div className="border-2 border-ccl-teal rounded-tile p-4 bg-white">
                <p className="text-sm text-ccl-teal uppercase tracking-wide">Vault</p>
                <p className="text-2xl font-display font-bold text-ccl-navy">
                  <CurrencyDisplay amount={player?.tl_vault || 0} />
                </p>
              </div>
            </div>

            {error && (
              <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            <div className="rounded-tile border-2 border-ccl-orange bg-gradient-to-r from-ccl-orange to-ccl-orange-deep text-white p-8 text-center mb-4">
              <h2 className="text-2xl font-display font-bold mb-2">Start Playing</h2>
              <p className="text-lg mb-4">Match the crowd&rsquo;s answers and earn coins based on your coverage.</p>
              <div className="flex items-center justify-center gap-2 mb-6 text-lg font-bold">
                <CurrencyDisplay amount={entryCost} iconClassName="w-5 h-5" textClassName="font-bold text-lg" />
              </div>
              {!canStartRound && errorReason && (
                <p className="mb-4 text-white text-sm">
                  {errorReason === 'insufficient_balance'
                    ? 'You need more coins to start a round.'
                    : 'Unable to start a round right now.'}
                </p>
              )}
              <button
                onClick={handleStartRound}
                disabled={isStartingRound || !canStartRound}
                className="bg-white text-ccl-orange font-bold py-3 px-8 rounded-tile shadow-tile hover:shadow-tile-sm transition-colors disabled:opacity-70"
              >
                {isStartingRound ? 'Starting round...' : 'Start'}
              </button>
            </div>

            <div className="rounded-tile border-2 border-ccl-teal bg-gradient-to-r from-ccl-teal to-ccl-teal-deep text-white p-6 text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <TrophyIcon className="w-8 h-8" />
                <h2 className="text-xl font-display font-bold">Challenges</h2>
              </div>
              <p className="mb-4">Compete in special challenges for exclusive rewards!</p>
              <button
                disabled
                className="bg-white text-ccl-teal font-bold py-2 px-6 rounded-tile shadow-tile opacity-50 cursor-not-allowed"
                title="Coming soon"
              >
                Coming Soon
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
