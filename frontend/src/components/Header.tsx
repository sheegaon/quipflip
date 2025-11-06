import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { BalanceFlipper } from './BalanceFlipper';
import { SubHeader } from './SubHeader';

export const Header: React.FC = () => {
  const { state, actions } = useGame();
  const { player, username } = state;
  const { logout, refreshDashboard, refreshBalance } = actions;
  const navigate = useNavigate();
  const location = useLocation();

  const [showGuestLogoutWarning, setShowGuestLogoutWarning] = React.useState(false);
  const [guestCredentials, setGuestCredentials] = React.useState<{ email: string | null; password: string | null } | null>(null);

  // Show back arrow on certain pages
  const isAdminRoute = location.pathname === '/admin' || location.pathname.startsWith('/admin/');
  const showBackArrow = location.pathname === '/statistics' || location.pathname === '/tracking' || location.pathname === '/quests' || location.pathname === '/results' || location.pathname === '/settings' || isAdminRoute;

  // Determine where back arrow should navigate based on current page
  const getBackNavigation = React.useCallback(() => {
    if (location.pathname === '/settings') {
      return '/statistics';
    }
    if (location.pathname === '/admin') {
      return '/settings';
    }
    if (location.pathname.startsWith('/admin/')) {
      return '/admin';
    }
    return '/dashboard';
  }, [location.pathname, isAdminRoute]);

  if (!player) {
    return null;
  }

  const goToStatistics = React.useCallback(() => {
    navigate('/statistics');
  }, [navigate]);

  const handleLogoClick = React.useCallback(async () => {
    // Refresh dashboard and balance before navigating
    try {
      await Promise.all([refreshDashboard(), refreshBalance()]);
    } catch (err) {
      console.warn('Failed to refresh from header icon:', err);
    }

    if (showBackArrow) {
      navigate(getBackNavigation());
    }
  }, [refreshDashboard, refreshBalance, showBackArrow, getBackNavigation, navigate]);

  const logoTitle = showBackArrow
    ? location.pathname === '/settings'
      ? 'Back to Statistics (refresh)'
      : 'Back to Dashboard (refresh)'
    : 'Refresh dashboard';

  const handleLogoutClick = React.useCallback(() => {
    if (!player?.is_guest) {
      logout();
      return;
    }

    let email: string | null = player.email ?? null;
    let password: string | null = null;

    if (typeof window !== 'undefined') {
      try {
        const stored = window.localStorage.getItem('quipflip_guest_credentials');
        if (stored) {
          const parsed = JSON.parse(stored) as { email?: string; password?: string };
          if (parsed.email) {
            email = parsed.email;
          }
          if (parsed.password) {
            password = parsed.password;
          }
        }
      } catch (err) {
        console.warn('Failed to read guest credentials from storage', err);
      }
    }

    setGuestCredentials({ email, password });
    setShowGuestLogoutWarning(true);
  }, [player?.is_guest, player?.email, logout]);

  const handleDismissGuestLogout = React.useCallback(() => {
    setShowGuestLogoutWarning(false);
    setGuestCredentials(null);
  }, []);

  const handleConfirmGuestLogout = React.useCallback(() => {
    setShowGuestLogoutWarning(false);
    setGuestCredentials(null);
    logout();
  }, [logout]);

  return (
    <>
      {showGuestLogoutWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-6">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="guest-logout-title"
            className="w-full max-w-xl bg-white rounded-tile shadow-tile-lg overflow-hidden"
          >
            <div className="p-6 space-y-6">
              <div className="space-y-2">
                <h2 id="guest-logout-title" className="text-2xl font-bold text-quip-navy">
                  Save Your Guest Login
                </h2>
                <p className="text-sm text-quip-navy opacity-80">
                  You&apos;ll need these details to sign back in after logging out. Keep a copy before you continue.
                </p>
              </div>

              <div className="tutorial-guest-credentials bg-gradient-to-r from-quip-orange to-quip-turquoise text-white p-6 rounded-tile shadow-lg space-y-4">
                <div>
                  <p className="font-semibold text-lg">Guest Credentials</p>
                  <p className="text-sm opacity-90">
                    Enter this email and password in the Returning Player form on the login page.
                  </p>
                </div>
                <div className="bg-white/15 p-4 rounded-lg backdrop-blur-sm space-y-2">
                  <p className="my-1 font-mono text-sm">
                    <strong>Email:</strong>{' '}
                    {guestCredentials?.email ?? 'Not available'}
                  </p>
                  {guestCredentials?.password ? (
                    <p className="my-1 font-mono text-sm">
                      <strong>Password:</strong> {guestCredentials.password}
                    </p>
                  ) : (
                    <p className="my-1 text-sm">
                      <strong>Password:</strong> QuipFlip
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-2 text-sm text-quip-navy">
                <p className="font-semibold">To log back in later:</p>
                <ol className="list-decimal pl-5 space-y-1">
                  <li>Visit the Quipflip login page and choose the &quot;Returning Player&quot; option.</li>
                  <li>Enter the guest email and password shown above.</li>
                  <li>Continue playing—your progress and coins stay with your guest account.</li>
                </ol>
              </div>

              <div className="flex flex-col gap-3 md:flex-row md:justify-end">
                <button
                  type="button"
                  onClick={handleDismissGuestLogout}
                  className="w-full md:w-auto rounded-tile border border-quip-teal px-4 py-2 text-quip-teal transition-colors hover:bg-quip-teal hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
                >
                  Stay Logged In
                </button>
                <button
                  type="button"
                  onClick={handleConfirmGuestLogout}
                  className="w-full md:w-auto rounded-tile bg-gradient-to-r from-quip-orange to-quip-turquoise px-4 py-2 font-semibold text-white shadow-md transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-turquoise"
                >
                  Log Out Now
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="bg-white shadow-tile-sm">
        <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
        <div className="flex justify-between items-center">
          {/* Left: Logo + Back Arrow (on certain pages) */}
          <div className="flex items-center gap-0.5 md:gap-3">
            <button
              type="button"
              onClick={handleLogoClick}
              className={`flex items-center gap-0 md:gap-2 cursor-pointer transition-opacity ${showBackArrow ? 'hover:opacity-80' : 'hover:opacity-90'}`}
              title={logoTitle}
              aria-label={logoTitle}
            >
              {showBackArrow && (
                <img
                  src="/icon_back_arrow.svg"
                  alt=""
                  className="w-5 h-5 md:w-7 md:h-7"
                  aria-hidden="true"
                />
              )}
              <img src="/large_icon.png" alt="Quipflip" className="md:h-10 h-6 w-auto" />
            </button>
          </div>

          {/* Center: Username (clickable to statistics) */}
          <div className="flex-1 text-center">
            <button
              onClick={goToStatistics}
              className="text-xs md:text-xl text-quip-turquoise font-semibold hover:text-quip-teal transition-colors"
              title="View your statistics"
            >
              {player.username || username}
            </button>
          </div>

          {/* Right: Flipcoins + Logout */}
          <div className="flex items-center gap-0.5 md:gap-4">
            {/* Flipcoin Balance */}
            <button
              type="button"
              onClick={goToStatistics}
              className="flex items-center gap-0.5 tutorial-balance border border-white/10 rounded-xl px-1 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
              title="View your statistics"
              aria-label="View your statistics"
            >
              <img src="/flipcoin.png" alt="Flipcoin" className="w-5 h-5 md:w-7 md:h-7" />
              <BalanceFlipper
                value={player.balance}
                className="text-xl md:text-2xl font-display font-bold text-quip-turquoise"
              />
            </button>
            {/* Logout Button */}
            <button onClick={handleLogoutClick} className="text-quip-teal hover:text-quip-turquoise" title="Logout">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 md:h-8 w-6 md:w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
    {/* Conditionally render SubHeader on dashboard */}
    {location.pathname === '/dashboard' && <SubHeader />}
    </>
  );
};
