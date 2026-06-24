import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiClient, extractErrorMessage } from '../api/client.ts';
import { clearStoredGuestCredentials } from '../utils/guestSession.ts';
import { GUEST_CREDENTIALS_KEY } from '../utils/storageKeys.ts';
import type {
  AuthTokenResponse,
  MagicLinkRequestResponse,
  MagicLinkStatusResponse,
} from '../api/types.ts';

type MagicLinkMode = 'save' | 'signin';

interface MagicLinkPanelProps {
  mode: MagicLinkMode;
  title: string;
  description: string;
  ctaLabel: string;
  className?: string;
  guestPlayerId?: string | null;
  initialEmail?: string;
  placeholder?: string;
  compact?: boolean;
  autoNavigateOnSuccess?: boolean;
  continueDestination?: string;
  continueLabel?: string;
  currentSummary?: string;
  savedSummary?: string;
  guestCredentialsStorageKey?: string;
  onAuthenticated?: (auth: AuthTokenResponse) => void | Promise<void>;
}

type PanelState = 'form' | 'requesting' | 'waiting' | 'consuming' | 'merge_required' | 'authenticated';

const TOKEN_PARAM_NAMES = ['magic_link_token', 'token'];

const getTokenFromLocation = (search: string): string | null => {
  const params = new URLSearchParams(search);
  for (const key of TOKEN_PARAM_NAMES) {
    const token = params.get(key);
    if (token) {
      return token;
    }
  }

  return null;
};

const formatExpiration = (expiresAt?: string | null): string | null => {
  if (!expiresAt) {
    return null;
  }

  const date = new Date(expiresAt);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

export const MagicLinkPanel: React.FC<MagicLinkPanelProps> = ({
  mode,
  title,
  description,
  ctaLabel,
  className = '',
  guestPlayerId = null,
  initialEmail = '',
  placeholder = 'tal@example.com',
  compact = false,
  autoNavigateOnSuccess = false,
  continueDestination = '/dashboard',
  continueLabel = 'Continue playing',
  currentSummary,
  savedSummary,
  guestCredentialsStorageKey = GUEST_CREDENTIALS_KEY,
  onAuthenticated,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const autoNavigateTimerRef = useRef<number | null>(null);
  const autoConsumeAttemptedRef = useRef(false);
  const pendingResolveTokenRef = useRef<string | null>(null);

  const [panelState, setPanelState] = useState<PanelState>('form');
  const [email, setEmail] = useState(initialEmail);
  const [error, setError] = useState<string | null>(null);
  const [requestResult, setRequestResult] = useState<MagicLinkRequestResponse | null>(null);
  const [statusResult, setStatusResult] = useState<MagicLinkStatusResponse | null>(null);

  const token = useMemo(() => getTokenFromLocation(location.search), [location.search]);

  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  useEffect(() => {
    return () => {
      if (autoNavigateTimerRef.current !== null) {
        window.clearTimeout(autoNavigateTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!token || autoConsumeAttemptedRef.current) {
      return;
    }

    autoConsumeAttemptedRef.current = true;
    pendingResolveTokenRef.current = token;
    clearMagicLinkTokenFromUrl(token);
    void consumeMagicLink(token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const scheduleAutoNavigate = (destination: string) => {
    if (!autoNavigateOnSuccess) {
      return;
    }

    if (autoNavigateTimerRef.current !== null) {
      window.clearTimeout(autoNavigateTimerRef.current);
    }

    autoNavigateTimerRef.current = window.setTimeout(() => {
      navigate(destination);
    }, 1300);
  };

  const clearMagicLinkTokenFromUrl = (magicLinkToken?: string | null) => {
    const tokenToClear = magicLinkToken ?? token;
    if (!tokenToClear) {
      return;
    }

    const params = new URLSearchParams(location.search);
    for (const key of TOKEN_PARAM_NAMES) {
      params.delete(key);
    }

    const nextSearch = params.toString();
    navigate(
      nextSearch ? `${location.pathname}?${nextSearch}` : location.pathname,
      { replace: true },
    );
  };

  const consumeMagicLink = async (magicLinkToken: string) => {
    try {
      setPanelState('consuming');
      setError(null);
      pendingResolveTokenRef.current = magicLinkToken;
      const result = await apiClient.consumeMagicLink({ token: magicLinkToken });
      setStatusResult(result);

      if (result.status === 'merge_required') {
        setPanelState('merge_required');
        return;
      }

      if (!result.auth) {
        throw new Error('magic_link_auth_incomplete');
      }

      clearMagicLinkTokenFromUrl(magicLinkToken);
      clearStoredGuestCredentials(guestCredentialsStorageKey);
      pendingResolveTokenRef.current = null;
      setPanelState('authenticated');
      await onAuthenticated?.(result.auth);
      scheduleAutoNavigate(continueDestination);
    } catch (err) {
      pendingResolveTokenRef.current = null;
      setStatusResult(null);
      setPanelState('form');
      setError(extractErrorMessage(err) || 'Unable to verify your link right now.');
    }
  };

  const handleResolve = async (mergeGuest: boolean) => {
    const resolveToken = pendingResolveTokenRef.current;
    if (!statusResult || !resolveToken) {
      return;
    }

    try {
      setPanelState('consuming');
      setError(null);
      const result = await apiClient.resolveMagicLink({
        token: resolveToken,
        merge_guest: mergeGuest,
      });
      setStatusResult(result);
      if (!result.auth) {
        throw new Error('magic_link_auth_incomplete');
      }

      clearMagicLinkTokenFromUrl(resolveToken);
      clearStoredGuestCredentials(guestCredentialsStorageKey);
      pendingResolveTokenRef.current = null;
      setPanelState('authenticated');
      await onAuthenticated?.(result.auth);
      scheduleAutoNavigate(continueDestination);
    } catch (err) {
      setPanelState('merge_required');
      setError(extractErrorMessage(err) || 'Unable to finish saving this account.');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError('Please enter an email address.');
      return;
    }

    try {
      setPanelState('requesting');
      setError(null);
      pendingResolveTokenRef.current = null;
      const result = await apiClient.requestMagicLink({
        email: normalizedEmail,
        guest_player_id: guestPlayerId ?? undefined,
        redirect_path: `${location.pathname}${location.search}`,
      });
      setRequestResult(result);
      setPanelState('waiting');
    } catch (err) {
      setPanelState('form');
      setError(extractErrorMessage(err) || 'Unable to send a sign-in link.');
    }
  };

  const renderSummary = (summary?: string) => {
    if (!summary) {
      return null;
    }

    return <p className="mt-1 text-sm text-slate-600">{summary}</p>;
  };

  const buttonText =
    panelState === 'requesting' ? 'Sending link...' :
    panelState === 'consuming' ? 'Checking link...' :
    ctaLabel;

  const isBusy = panelState === 'requesting' || panelState === 'consuming';

  return (
    <div className={className}>
      {panelState === 'merge_required' && statusResult?.guest_player && statusResult?.saved_player ? (
        <div className="space-y-4">
          <div>
            <h3 className={`${compact ? 'text-lg' : 'text-2xl'} font-display font-bold text-slate-900`}>{title}</h3>
            <p className="mt-2 text-slate-700">{description}</p>
          </div>

          {error && (
            <div className="rounded-tile border border-red-300 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-tile border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Current device</p>
              <p className="mt-1 font-semibold text-slate-900">
                {statusResult.guest_player.username}
              </p>
              {renderSummary(currentSummary)}
            </div>
            <div className="rounded-tile border border-slate-200 bg-white p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Saved account</p>
              <p className="mt-1 font-semibold text-slate-900">
                {statusResult.saved_player.username}
              </p>
              {renderSummary(savedSummary)}
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => void handleResolve(true)}
              disabled={isBusy}
              className="rounded-tile bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Add these games to my account
            </button>
            <button
              type="button"
              onClick={() => void handleResolve(false)}
              disabled={isBusy}
              className="rounded-tile border border-slate-300 bg-white px-4 py-3 font-semibold text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Sign in without adding them
            </button>
          </div>
        </div>
      ) : panelState === 'authenticated' ? (
        <div className="space-y-4">
          <div>
            <h3 className={`${compact ? 'text-lg' : 'text-2xl'} font-display font-bold text-slate-900`}>Account saved</h3>
            <p className="mt-2 text-slate-700">
              Your name, stats, awards, and history are now available on other devices.
            </p>
          </div>

          <div className="rounded-tile border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
            <p className="font-semibold">Saved successfully</p>
            <p className="mt-1 text-sm">
              {mode === 'signin'
                ? 'You can continue on this device while the account stays available everywhere.'
                : 'Keep playing; this device remains signed in.'}
            </p>
          </div>

          {autoNavigateOnSuccess ? (
            <p className="text-sm text-slate-600">Redirecting to your game…</p>
          ) : (
            <button
              type="button"
              onClick={() => navigate(continueDestination)}
              className="rounded-tile bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-slate-700"
            >
              {continueLabel}
            </button>
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <h3 className={`${compact ? 'text-lg' : 'text-2xl'} font-display font-bold text-slate-900`}>{title}</h3>
            <p className="mt-2 text-slate-700">{description}</p>
          </div>

          {error && (
            <div className="rounded-tile border border-red-300 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          {panelState === 'waiting' && requestResult ? (
            <div className="rounded-tile border border-slate-200 bg-white p-4">
              <p className="font-semibold text-slate-900">Check your email</p>
              <p className="mt-1 text-sm text-slate-700">
                We sent a sign-in link to <span className="font-medium">{requestResult.email}</span>.
              </p>
              {formatExpiration(requestResult.expires_at) && (
                <p className="mt-2 text-xs text-slate-500">
                  The link expires around {formatExpiration(requestResult.expires_at)}.
                </p>
              )}
              <button
                type="button"
                onClick={() => {
                  setPanelState('form');
                  setRequestResult(null);
                }}
                className="mt-4 rounded-tile border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-50"
              >
                Send another link
              </button>
            </div>
          ) : (
            <>
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder={placeholder}
                  autoComplete="email"
                  className="w-full rounded-tile border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-slate-500"
                  disabled={isBusy}
                />
              </label>

              <button
                type="submit"
                disabled={isBusy}
                className="rounded-tile bg-slate-900 px-4 py-3 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {buttonText}
              </button>

              <p className="text-xs text-slate-500">
                No password needed. We’ll keep the guest session active while the link is sent.
              </p>
            </>
          )}
        </form>
      )}
    </div>
  );
};

export default MagicLinkPanel;
