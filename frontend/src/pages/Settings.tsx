import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '../api/client';
import { settingsLogger } from '../utils/logger';

const Settings: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const { resetTutorial } = useTutorial();
  const navigate = useNavigate();
  const [resettingTutorial, setResettingTutorial] = useState(false);
  const [tutorialResetSuccess, setTutorialResetSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdminPasswordPrompt, setShowAdminPasswordPrompt] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [adminPasswordError, setAdminPasswordError] = useState<string | null>(null);

  if (!player) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    );
  }

  const handleResetTutorial = async () => {
    try {
      setResettingTutorial(true);
      setError(null);
      setTutorialResetSuccess(false);
      settingsLogger.debug('Resetting tutorial progress');
      resetTutorial();
      setTutorialResetSuccess(true);
      settingsLogger.info('Tutorial progress reset');
      setTimeout(() => setTutorialResetSuccess(false), 3000);
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to reset tutorial';
      settingsLogger.error('Failed to reset tutorial', err);
      setError(message);
    } finally {
      setResettingTutorial(false);
      settingsLogger.debug('Reset tutorial flow completed');
    }
  };

  const handleAdminAccess = () => {
    setShowAdminPasswordPrompt(true);
    setAdminPassword('');
    setAdminPasswordError(null);
    settingsLogger.debug('Admin access prompt opened');
  };

  const handleAdminPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdminPasswordError(null);

    // Validate the password against the backend secret_key
    try {
      const result = await apiClient.validateAdminPassword(adminPassword);

      if (result.valid) {
        // Password is correct, navigate to admin
        settingsLogger.info('Admin password validated, navigating to admin');
        navigate('/admin');
      } else {
        setAdminPasswordError('Incorrect admin password');
        settingsLogger.warn('Invalid admin password provided');
      }
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to verify password';
      settingsLogger.error('Failed to validate admin password', err);
      setAdminPasswordError(message);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Settings</h1>
          <p className="text-quip-teal mt-1">Manage your account and preferences</p>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="tile-card p-4 mb-6 bg-red-100 border-2 border-red-400">
            <div className="flex justify-between items-start">
              <span className="text-red-700">{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-2 text-red-900 hover:text-red-700"
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {tutorialResetSuccess && (
          <div className="tile-card p-4 mb-6 bg-green-100 border-2 border-green-400">
            <div className="flex justify-between items-start">
              <span className="text-green-700">Tutorial reset successfully!</span>
              <button
                onClick={() => setTutorialResetSuccess(false)}
                className="ml-2 text-green-900 hover:text-green-700"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Account Information */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Account Information</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Username</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {player.username}
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Email</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {player.email}
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Anonymous Pseudonym</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {player.pseudonym}
                </div>
                <p className="text-xs text-quip-teal mt-1">This is how other players see you in results</p>
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Account Created</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {formatDate(player.created_at)}
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Last Login</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {formatDate(player.last_login_date)}
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-1">Outstanding Prompts</label>
                <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                  {player.outstanding_prompts} / 10
                </div>
                <p className="text-xs text-quip-teal mt-1">Active prompts waiting for copies</p>
              </div>
            </div>
          </div>
        </div>

        {/* Balance Information */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Balance Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Current Balance</label>
              <div className="bg-white border-2 border-quip-orange border-opacity-30 rounded-tile p-3">
                <div className="flex items-center gap-2">
                  <img src="/flipcoin.png" alt="Flipcoin" className="w-6 h-6" />
                  <span className="text-2xl font-bold text-quip-orange">{player.balance}</span>
                </div>
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Starting Balance</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                <div className="flex items-center gap-2">
                  <img src="/flipcoin.png" alt="Flipcoin" className="w-6 h-6" />
                  <span className="text-2xl font-bold text-quip-orange">{player.starting_balance}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tutorial Management */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Tutorial</h2>
          <p className="text-quip-teal mb-4">
            Reset the tutorial to see the introduction and walkthrough again.
          </p>
          <button
            onClick={handleResetTutorial}
            disabled={resettingTutorial}
            className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
          >
            {resettingTutorial ? 'Resetting...' : 'Reset Tutorial'}
          </button>
        </div>

        {/* Admin Access */}
        <div className="tile-card p-6 mb-6 border-2 border-quip-orange border-opacity-30">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Admin Access</h2>
          <p className="text-quip-teal mb-4">
            Access administrative settings and configuration. Requires the application admin password (secret key).
          </p>

          {!showAdminPasswordPrompt ? (
            <button
              onClick={handleAdminAccess}
              className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Access Admin Panel
            </button>
          ) : (
            <form onSubmit={handleAdminPasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-2">
                  Enter admin password (secret key)
                </label>
                <input
                  type="password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className="w-full md:w-96 border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                  placeholder="Admin password"
                  autoFocus
                />
                {adminPasswordError && (
                  <p className="text-red-600 text-sm mt-1">{adminPasswordError}</p>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  type="submit"
                  className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  Continue
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAdminPasswordPrompt(false);
                    setAdminPassword('');
                    setAdminPasswordError(null);
                  }}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-700 font-bold py-3 px-6 rounded-tile transition-all"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Future Features (Placeholder) */}
        <div className="tile-card p-6 mb-6 bg-gray-50 border-2 border-gray-300 opacity-60">
          <h2 className="text-2xl font-display font-bold text-gray-600 mb-4">Coming Soon</h2>
          <ul className="space-y-2 text-gray-600">
            <li className="flex items-center gap-2">
              <span className="text-gray-400">🔒</span>
              Change Password
            </li>
            <li className="flex items-center gap-2">
              <span className="text-gray-400">✉️</span>
              Change Email Address
            </li>
            <li className="flex items-center gap-2">
              <span className="text-gray-400">📊</span>
              Export Account Data
            </li>
            <li className="flex items-center gap-2">
              <span className="text-gray-400">🗑️</span>
              Delete Account
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Settings;
