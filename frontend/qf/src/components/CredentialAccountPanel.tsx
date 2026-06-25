import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import { clearStoredGuestCredentials } from '@crowdcraft/utils/guestSession.ts';
import { useGame } from '../contexts/GameContext';

type CredentialAccountMode = 'signin' | 'upgrade';

interface CredentialAccountPanelProps {
  mode: CredentialAccountMode;
  title: string;
  description: string;
  ctaLabel: string;
  className?: string;
  emailPlaceholder?: string;
  navigateOnSuccess?: boolean;
  continueDestination?: string;
  currentSummary?: string;
}

const CredentialAccountPanel: React.FC<CredentialAccountPanelProps> = ({
  mode,
  title,
  description,
  ctaLabel,
  className = '',
  emailPlaceholder = 'tal@example.com',
  navigateOnSuccess = false,
  continueDestination = '/dashboard',
  currentSummary,
}) => {
  const navigate = useNavigate();
  const { state, actions } = useGame();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isUpgrade = mode === 'upgrade';

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError('Please enter an email address.');
      return;
    }

    if (!password) {
      setError('Please enter a password.');
      return;
    }

    if (isUpgrade) {
      if (!state.player?.is_guest) {
        setError('This action is only available for guest accounts.');
        return;
      }

      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const response = isUpgrade
        ? await apiClient.upgradeGuest({ email: normalizedEmail, password })
        : await apiClient.login({ email: normalizedEmail, password });

      clearStoredGuestCredentials();
      actions.startSession(response.player.username);
      await actions.refreshDashboard();
      await actions.refreshBalance();

      if (navigateOnSuccess) {
        navigate(continueDestination);
      }
    } catch (err) {
      const fallbackMessage = isUpgrade
        ? 'Unable to save your account right now.'
        : 'Unable to sign in right now.';
      setError(extractErrorMessage(err) || fallbackMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={className}>
      <div>
        <h3 className="text-2xl font-display font-bold text-slate-900">{title}</h3>
        <p className="mt-2 text-slate-700">{description}</p>
        {currentSummary ? (
          <p className="mt-2 text-sm text-slate-600">{currentSummary}</p>
        ) : null}
      </div>

      {error ? (
        <div className="mt-4 rounded-tile border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="flex flex-col">
          <label className="mb-2 text-sm font-semibold text-slate-700">Email</label>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded-tile border-2 border-slate-300 bg-white p-3 text-slate-900 focus:border-ccl-orange focus:outline-none"
            placeholder={emailPlaceholder}
            disabled={isSubmitting}
          />
        </div>

        <div className="flex flex-col">
          <label className="mb-2 text-sm font-semibold text-slate-700">Password</label>
          <input
            type="password"
            autoComplete={isUpgrade ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded-tile border-2 border-slate-300 bg-white p-3 text-slate-900 focus:border-ccl-orange focus:outline-none"
            placeholder={isUpgrade ? 'Create a password' : 'Enter your password'}
            disabled={isSubmitting}
          />
          {isUpgrade ? (
            <p className="mt-2 text-xs text-slate-500">
              Use at least 8 characters with uppercase, lowercase, and a number.
            </p>
          ) : null}
        </div>

        {isUpgrade ? (
          <div className="flex flex-col">
            <label className="mb-2 text-sm font-semibold text-slate-700">Confirm password</label>
            <input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="rounded-tile border-2 border-slate-300 bg-white p-3 text-slate-900 focus:border-ccl-orange focus:outline-none"
              placeholder="Confirm your password"
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-tile bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isSubmitting ? (isUpgrade ? 'Saving account...' : 'Signing in...') : ctaLabel}
        </button>
      </form>
    </div>
  );
};

export default CredentialAccountPanel;
