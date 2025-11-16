import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Header from '../components/Header';

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
    upgradeGuest,
  } = useIRGame();

  const [showUpgradeForm, setShowUpgradeForm] = useState(false);
  const [upgradeEmail, setUpgradeEmail] = useState('');
  const [upgradePassword, setUpgradePassword] = useState('');

  // Initialize dashboard on component mount with proper error handling
  useEffect(() => {
    const controller = new AbortController();

    // Use a separate promise handler to avoid "Uncaught (in promise)" errors
    refreshDashboard()
      .catch((err) => {
        // Only log if the request wasn't aborted
        if (controller.signal.aborted) {
          return;
        }
        console.error('Failed to initialize dashboard:', err);
      });

    return () => {
      controller.abort();
    };
  }, [refreshDashboard]);

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
    } catch (err) {
      console.error('Failed to claim bonus:', err);
    }
  };

  const handleUpgrade = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await upgradeGuest(upgradeEmail, upgradePassword);
      setShowUpgradeForm(false);
      setUpgradeEmail('');
      setUpgradePassword('');
    } catch (err) {
      console.error('Failed to upgrade account:', err);
    }
  };

  const handleViewResult = (setId: string) => {
    navigate(`/results/${setId}`);
  };

  if (!player) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Header />
        <div className="container mx-auto px-4 py-8 text-center">
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg flex justify-between items-center">
            <span>{error}</span>
            <button onClick={clearError} className="text-red-700 hover:text-red-900">
              ✕
            </button>
          </div>
        )}

        {/* Guest Account Upgrade Banner */}
        {player.is_guest && (
          <div className="mb-6 p-4 bg-yellow-100 border border-yellow-400 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-yellow-800">Playing as Guest</h3>
                <p className="text-sm text-yellow-700">
                  Upgrade to a full account to save your progress across devices!
                </p>
              </div>
              <button
                onClick={() => setShowUpgradeForm(!showUpgradeForm)}
                className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors"
              >
                Upgrade
              </button>
            </div>

            {/* Upgrade Form */}
            {showUpgradeForm && (
              <form onSubmit={handleUpgrade} className="mt-4 space-y-3">
                <input
                  type="email"
                  value={upgradeEmail}
                  onChange={(e) => setUpgradeEmail(e.target.value)}
                  placeholder="Email"
                  required
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500"
                />
                <input
                  type="password"
                  value={upgradePassword}
                  onChange={(e) => setUpgradePassword(e.target.value)}
                  placeholder="Password (min 6 characters)"
                  required
                  minLength={6}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-500"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors disabled:opacity-50"
                >
                  {loading ? 'Upgrading...' : 'Confirm Upgrade'}
                </button>
              </form>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Main Actions Card */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Quick Actions</h2>

            {/* Daily Bonus */}
            {player.daily_bonus_available && (
              <button
                onClick={handleClaimBonus}
                disabled={loading}
                className="w-full mb-4 py-3 px-4 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-semibold rounded-lg hover:from-green-600 hover:to-emerald-600 transition-all shadow-lg disabled:opacity-50"
              >
                🎁 Claim Daily Bonus (100 IC)
              </button>
            )}

            {/* Start Battle Button */}
            <button
              onClick={handleStartBattle}
              disabled={loading || !!activeSet}
              className="w-full py-4 px-6 bg-gradient-to-r from-purple-500 to-indigo-500 text-white font-bold text-lg rounded-lg hover:from-purple-600 hover:to-indigo-600 transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {activeSet ? '⚠️ Battle in Progress' : '🚀 Start Backronym Battle'}
            </button>

            {activeSet && (
              <div className="mt-4 p-4 bg-indigo-100 border border-indigo-300 rounded-lg">
                <p className="text-sm text-indigo-800 font-semibold">
                  Active Battle: <span className="text-lg">{activeSet.word.toUpperCase()}</span>
                </p>
                <p className="text-xs text-indigo-600 mt-1">
                  Status: {activeSet.status.toUpperCase()}
                </p>
                <button
                  onClick={() => {
                    if (activeSet.status === 'open') {
                      navigate('/create');
                    } else if (activeSet.status === 'voting') {
                      navigate('/voting/' + activeSet.set_id);
                    }
                  }}
                  className="mt-2 w-full py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors"
                >
                  Continue Battle
                </button>
              </div>
            )}

            <div className="mt-6 text-center text-sm text-gray-600">
              <p className="mb-2">Entry Cost: 100 IC</p>
              <p>Win InitCoins based on votes received!</p>
            </div>
          </div>

          {/* Pending Results Card */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Pending Results</h2>

            {pendingResults.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p className="text-4xl mb-2">📊</p>
                <p>No pending results</p>
                <p className="text-sm">Complete battles to see results here</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pendingResults.map((result) => (
                  <div
                    key={result.set_id}
                    className="p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg hover:shadow-md transition-shadow"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-semibold text-gray-800">
                          Word: {result.word.toUpperCase()}
                        </p>
                        <p className="text-sm text-gray-600">
                          Payout: {result.payout_amount > 0 ? '+' : ''}
                          {result.payout_amount} IC
                        </p>
                      </div>
                      <button
                        onClick={() => handleViewResult(result.set_id)}
                        className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors"
                      >
                        View
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Stats Preview (Optional) */}
        <div className="mt-6 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Your Stats</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <p className="text-3xl font-bold text-purple-600">{player.wallet}</p>
              <p className="text-sm text-gray-600">Wallet IC</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-3xl font-bold text-green-600">{player.vault}</p>
              <p className="text-sm text-gray-600">Vault IC</p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <p className="text-3xl font-bold text-blue-600">-</p>
              <p className="text-sm text-gray-600">Battles Won</p>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <p className="text-3xl font-bold text-yellow-600">-</p>
              <p className="text-sm text-gray-600">Vote Accuracy</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
