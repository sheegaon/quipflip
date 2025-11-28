import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { dashboardLogger } from '../utils/logger';

const getErrorDetail = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  return (error as { detail?: string }).detail;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface UpgradeGuestAccountProps {
  className?: string;
}

export const UpgradeGuestAccount: React.FC<UpgradeGuestAccountProps> = ({ className = '' }) => {
  const { actions } = useGame();
  const navigate = useNavigate();
  
  const [isExpanded, setIsExpanded] = useState(false);
  const [upgradeForm, setUpgradeForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [upgradeError, setUpgradeError] = useState<string | null>(null);
  const [upgradeSuccess, setUpgradeSuccess] = useState<string | null>(null);
  const [upgradeLoading, setUpgradeLoading] = useState(false);

  useEffect(() => {
    if (!upgradeSuccess) {
      return undefined;
    }

    const timer = setTimeout(() => {
      navigate('/dashboard');
    }, 2000);

    return () => clearTimeout(timer);
  }, [navigate, upgradeSuccess]);

  const handleUpgradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpgradeError(null);
    setUpgradeSuccess(null);

    if (!emailPattern.test(upgradeForm.email)) {
      setUpgradeError('Please enter a valid email address.');
      return;
    }

    if (!upgradeForm.password || upgradeForm.password.length < 8) {
      setUpgradeError('Password must be at least 8 characters long.');
      return;
    }

    if (!upgradeForm.confirmPassword) {
      setUpgradeError('Please confirm your password to upgrade.');
      return;
    }

    if (upgradeForm.password !== upgradeForm.confirmPassword) {
      setUpgradeError('Passwords do not match.');
      return;
    }

    try {
      setUpgradeLoading(true);
      dashboardLogger.info('Upgrading guest account');

      await apiClient.upgradeGuest({
        email: upgradeForm.email.trim(),
        password: upgradeForm.password,
      });

      dashboardLogger.info('Guest account upgraded successfully');
      setUpgradeSuccess('Account upgraded successfully! You can now log in with your new credentials.');
      setUpgradeForm({ email: '', password: '', confirmPassword: '' });
      await actions.refreshBalance();
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'not_a_guest') {
        setUpgradeError('This account is already a full account.');
      } else if (getErrorDetail(err) === 'email_taken') {
        setUpgradeError('That email address is already in use.');
      } else {
        setUpgradeError(extractErrorMessage(err) || 'Failed to upgrade account');
      }
      dashboardLogger.error('Failed to upgrade guest account', err);
    } finally {
      setUpgradeLoading(false);
    }
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpgradeError(null);
    setUpgradeSuccess(null);

    if (!emailPattern.test(upgradeForm.email)) {
      setUpgradeError('Please enter a valid email address.');
      return;
    }

    if (!upgradeForm.password) {
      setUpgradeError('Please enter your password.');
      return;
    }

    try {
      setUpgradeLoading(true);
      dashboardLogger.info('Logging into existing account');

      const response = await apiClient.login({
        email: upgradeForm.email.trim(),
        password: upgradeForm.password,
      });

      dashboardLogger.info('Login from upgrade modal successful');
      actions.startSession(response.username);
      await actions.refreshBalance();
      navigate('/dashboard');
    } catch (err: unknown) {
      setUpgradeError(extractErrorMessage(err) || 'Failed to log in');
      dashboardLogger.error('Failed to log in from upgrade modal', err);
    } finally {
      setUpgradeLoading(false);
    }
  };

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={`bg-gradient-to-br from-orange-50 to-cyan-50 border-2 border-quip-orange rounded-tile mb-4 ${className}`}>
      <button
        onClick={toggleExpanded}
        className="w-full px-4 py-3 text-left focus:outline-none rounded-tile"
        aria-expanded={isExpanded}
        aria-controls="upgrade-content"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-display font-bold text-quip-navy">
            Upgrade Your Guest Account
          </h2>
          <svg
            className={`w-5 h-5 text-quip-navy transition-transform duration-200 ${
              isExpanded ? 'transform rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      <div
        id="upgrade-content"
        className={`transition-all duration-300 ease-in-out overflow-hidden ${
          isExpanded ? 'max-h-screen opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="px-4 pb-4">
          <p className="text-quip-navy mb-4">
            You're currently using a guest account with limited access. Upgrade to a full account to:
          </p>
          <ul className="list-disc list-inside text-quip-navy mb-4 space-y-1">
            <li>Save your progress permanently</li>
            <li>Access your account from any device</li>
            <li>Never lose your Flipcoins and stats</li>
            <li>Get higher rate limits for smoother gameplay</li>
          </ul>
          {upgradeError && <p className="text-red-600 mb-3">{upgradeError}</p>}
          {upgradeSuccess && <p className="text-green-600 mb-3">{upgradeSuccess}</p>}
          <form onSubmit={handleUpgradeSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-quip-teal mb-2">Email Address</label>
                <input
                  type="email"
                  value={upgradeForm.email}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, email: e.target.value }))}
                  className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange bg-white"
                  placeholder="your@email.com"
                  disabled={upgradeLoading}
                  required
                />
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-quip-teal mb-2">Password</label>
                <input
                  type="password"
                  value={upgradeForm.password}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, password: e.target.value }))}
                  className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange bg-white"
                  placeholder="Min 8 characters"
                  disabled={upgradeLoading}
                  minLength={8}
                  required
                />
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-quip-teal mb-2">Confirm Password</label>
                <input
                  type="password"
                  value={upgradeForm.confirmPassword}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                  className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange bg-white"
                  placeholder="Re-enter password"
                  disabled={upgradeLoading}
                  minLength={8}
                />
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={handleLoginSubmit}
                disabled={upgradeLoading}
                className="bg-white border-2 border-quip-navy text-quip-navy hover:bg-quip-navy hover:text-white disabled:bg-gray-100 disabled:text-gray-500 disabled:border-gray-300 font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {upgradeLoading ? 'Logging in...' : 'Login'}
              </button>
              <button
                type="submit"
                disabled={upgradeLoading}
                className="bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {upgradeLoading ? 'Upgrading...' : 'Upgrade Account'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default UpgradeGuestAccount;