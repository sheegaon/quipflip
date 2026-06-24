import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Header from '../components/Header';
import InitCoinDisplay from '../components/InitCoinDisplay';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';
import MagicLinkPanel from '@crowdcraft/components/MagicLinkPanel.tsx';
import { useTutorial } from '../contexts/TutorialContext';
import { Pagination } from '../components/Pagination';
import { GUEST_CREDENTIALS_KEY } from '../utils/storageKeys';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const {
    player,
    activeSet,
    pendingResults,
    loading,
    error,
    startBackronymBattle,
    claimDailyBonus,
    refreshDashboard,
    clearError,
  } = useIRGame();
  const { startTutorial, skipTutorial, tutorialStatus } = useTutorial();

  const RESULTS_PER_PAGE = 3;
  const [resultsPage, setResultsPage] = useState(1);

  // Initialize dashboard on component mount with proper error handling
  useEffect(() => {
    const controller = new AbortController();

    refreshDashboard()
      .catch((err) => {
        if (controller.signal.aborted) {
          return;
        }
        console.error('Failed to initialize dashboard:', err);
      });

    return () => {
      controller.abort();
    };
  }, [refreshDashboard]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(pendingResults.length / RESULTS_PER_PAGE));
    if (resultsPage > totalPages) {
      setResultsPage(totalPages);
    }
  }, [pendingResults, resultsPage]);

  const handleStartBattle = async () => {
    try {
      await startBackronymBattle();
      navigate('/create');
    } catch (err) {
      console.error('Failed to start battle:', err);
    }
  };

  const handleClaimBonus = async () => {
    try {
      await claimDailyBonus();
      // Refresh dashboard to update treasure chest icon and player balance
      await refreshDashboard();
    } catch (err) {
      console.error('Failed to claim bonus:', err);
    }
  };

  const handleViewResult = (setId: string) => {
    navigate(`/results/${setId}`);
  };

  if (!player) {
    return (
      <div className="min-h-screen bg-ir-cream bg-pattern">
        <Header />
        <div className="max-w-4xl mx-auto md:px-4 px-3 md:pt-8 pt-3 text-center">
          <p className="text-ir-teal">Loading...</p>
        </div>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(pendingResults.length / RESULTS_PER_PAGE));
  const paginatedResults = pendingResults.slice(
    (resultsPage - 1) * RESULTS_PER_PAGE,
    resultsPage * RESULTS_PER_PAGE
  );

  return (
    <div className="min-h-screen bg-ir-cream bg-pattern">
      <Header />

      {tutorialStatus === 'inactive' && (
        <TutorialWelcome onStart={startTutorial} onSkip={skipTutorial} />
      )}

      <div className="max-w-4xl mx-auto md:px-4 px-3 md:pt-8 pt-3 md:pb-5 pb-5">
        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile flex justify-between items-center">
            <span>{error}</span>
            <button onClick={clearError} className="text-red-700 hover:text-red-900 font-bold text-xl">
              ✕
            </button>
          </div>
        )}

        {/* Guest Save Prompt */}
        {player.is_guest && pendingResults.length > 0 && (
          <div className="mb-6 tile-card p-4 bg-ir-orange bg-opacity-10 border-2 border-ir-orange slide-up-enter">
            <MagicLinkPanel
              mode="save"
              title="Keep your stats"
              description="Save your name, wins, awards, and history across devices."
              ctaLabel="Save my account"
              guestPlayerId={player.player_id}
              autoNavigateOnSuccess
              continueDestination="/dashboard"
              continueLabel="Continue playing"
              guestCredentialsStorageKey={GUEST_CREDENTIALS_KEY}
            />
          </div>
        )}

        {/* Active Set Notification */}
        {activeSet && (
          <div className="tile-card bg-ir-turquoise bg-opacity-10 border-2 border-ir-turquoise p-4 mb-6 slide-up-enter">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex-1">
                <p className="font-display font-semibold text-ir-turquoise text-lg">
                  Active Battle: {activeSet.word.toUpperCase()}
                </p>
                <p className="text-sm text-ir-teal mt-1">
                  Status: <span className="font-semibold">{activeSet.status.charAt(0).toUpperCase() + activeSet.status.slice(1)}</span>
                </p>
              </div>
              <button
                onClick={() => {
                  if (activeSet.status === 'open') {
                    navigate('/create');
                  } else if (activeSet.status === 'voting') {
                    navigate('/voting/' + activeSet.set_id);
                  }
                }}
                className="w-full sm:w-auto bg-ir-turquoise hover:bg-ir-teal text-white font-bold py-2 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                Continue Battle
              </button>
            </div>
          </div>
        )}

        {/* Main Action Card */}
        <div className="tile-card md:p-6 p-3 mb-6 shuffle-enter tutorial-dashboard">
          <h2 className="text-2xl font-display font-bold mb-4 text-ir-navy">Backronym Battle</h2>

          {/* Daily Bonus */}
          {player.daily_bonus_available && (
            <button
              onClick={handleClaimBonus}
              disabled={loading}
              className="w-full mb-4 py-3 px-4 bg-gradient-to-r from-ir-turquoise to-ir-teal text-white font-semibold rounded-tile hover:shadow-tile-sm transition-all shadow-tile disabled:opacity-50"
            >
              🎁 Claim Daily Bonus (100 IC)
            </button>
          )}

          {/* Start Battle Button */}
          <div className="border-2 border-ir-navy rounded-tile p-4 bg-ir-navy bg-opacity-5 hover:bg-opacity-10 transition-all">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-display font-semibold text-lg text-ir-navy">Start Battle</h3>
              <span className="text-ir-orange-deep font-bold flex items-center gap-1">
                <InitCoinDisplay amount={100} iconClassName="w-4 h-4" textClassName="font-bold" />
              </span>
            </div>
            <p className="text-sm text-ir-teal mb-3">
              Create a backronym and compete for InitCoins
            </p>
            <button
              onClick={handleStartBattle}
              disabled={loading || !!activeSet}
              className="w-full bg-ir-navy hover:bg-ir-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
            >
              {activeSet ? 'Battle in Progress' : 'Start Backronym Battle'}
            </button>
          </div>
        </div>

        {/* Pending Results Card - Hidden for guests */}
        {!player.is_guest && (
          <div className="tile-card md:p-6 p-3 shuffle-enter">
            <h2 className="text-2xl font-display font-bold mb-4 text-ir-navy">Pending Results</h2>

            {pendingResults.length === 0 ? (
              <div className="text-center py-8 text-ir-teal">
                <p className="text-4xl mb-2">📊</p>
                <p className="font-semibold">No pending results</p>
                <p className="text-sm">Complete battles to see results here</p>
              </div>
            ) : (
              <div className="space-y-3">
                {paginatedResults.map((result) => (
                  <div
                    key={result.set_id}
                    className="p-4 bg-ir-teal-light border-2 border-ir-turquoise rounded-tile hover:shadow-tile-sm transition-all"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-display font-semibold text-ir-navy">
                          Word: {result.word.toUpperCase()}
                        </p>
                        <p className="text-sm text-ir-teal">
                          Payout: <span className={`font-bold ${result.payout_amount > 0 ? 'text-ir-turquoise' : 'text-ir-orange'}`}>
                            {result.payout_amount > 0 ? '+' : ''}
                            {result.payout_amount} IC
                          </span>
                        </p>
                      </div>
                      <button
                        onClick={() => handleViewResult(result.set_id)}
                        className="px-4 py-2 bg-ir-turquoise text-white rounded-tile hover:bg-ir-teal transition-colors font-semibold"
                      >
                        View
                      </button>
                    </div>
                  </div>
                ))}
                {pendingResults.length > RESULTS_PER_PAGE && (
                  <Pagination
                    currentPage={resultsPage}
                    totalPages={totalPages}
                    onPageChange={setResultsPage}
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
