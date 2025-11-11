import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { BalanceFlipper } from './BalanceFlipper';
import { SubHeader } from './SubHeader';
import { HomeIcon } from './icons/HomeIcon';
import { TreasureChestIcon } from './TreasureChestIcon';
import { SurveyIcon } from './icons/SurveyIcon';
import { CogIcon } from './icons/CogIcon';

export const Header: React.FC = () => {
  const { state, actions } = useGame();
  const { player, username } = state;
  const { logout, refreshDashboard, refreshBalance } = actions;
  const navigate = useNavigate();
  const location = useLocation();

  const [showGuestLogoutWarning, setShowGuestLogoutWarning] = React.useState(false);
  const [guestCredentials, setGuestCredentials] = React.useState<{ email: string | null; password: string | null } | null>(null);
  const [showDropdown, setShowDropdown] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Show back arrow on certain pages
  const isAdminRoute = location.pathname === '/admin' || location.pathname.startsWith('/admin/');
  const backArrowPaths = ['/statistics', '/leaderboard', '/tracking', '/quests', '/results', '/settings', '/completed', '/online-users'];
  const showBackArrow = backArrowPaths.includes(location.pathname) || isAdminRoute;

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

  const handleLogoClick = React.useCallback(() => {
    setShowDropdown(prevShowDropdown => !prevShowDropdown);
  }, []);

  const handleBackArrowClick = React.useCallback(async () => {
    // Refresh dashboard and balance before navigating
    try {
      await Promise.all([refreshDashboard(), refreshBalance()]);
    } catch (err) {
      console.warn('Failed to refresh from header icon:', err);
    }

    navigate(getBackNavigation());
  }, [refreshDashboard, refreshBalance, getBackNavigation, navigate]);

  const logoTitle = 'Open menu';
  const backArrowTitle = location.pathname === '/settings'
    ? 'Back to Statistics (refresh)'
    : 'Back to Dashboard (refresh)';

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

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDropdown]);

  const handleNavigate = React.useCallback((path: string) => {
    setShowDropdown(false);
    navigate(path);
  }, [navigate]);

  return (
    <>
      {showGuestLogoutWarning && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4 py-6">
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
                  onClick={handleConfirmGuestLogout}
                  className="w-full md:w-auto rounded-tile border border-quip-teal px-4 py-2 text-quip-teal transition-colors hover:bg-quip-teal hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
                >
                  Log Out Now
                </button>
                <button
                  type="button"
                  onClick={handleDismissGuestLogout}
                  className="w-full md:w-auto rounded-tile bg-gradient-to-r from-quip-orange to-quip-turquoise px-4 py-2 font-semibold text-white shadow-md transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-turquoise"
                >
                  Stay Logged In
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
          <div className="flex items-center gap-0.5 md:gap-3 relative">
            {showBackArrow && (
              <button
                type="button"
                onClick={handleBackArrowClick}
                className="cursor-pointer transition-opacity hover:opacity-80"
                title={backArrowTitle}
                aria-label={backArrowTitle}
              >
                <img
                  src="/icon_arrow_left.svg"
                  alt=""
                  className="w-7 h-7 md:w-9 md:h-9"
                  aria-hidden="true"
                />
              </button>
            )}
            <button
              type="button"
              onClick={handleLogoClick}
              className="cursor-pointer transition-opacity hover:opacity-90"
              title={logoTitle}
              aria-label={logoTitle}
            >
              <img src="/large_icon.png" alt="Quipflip" className="md:h-11 h-9 w-auto" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div
                ref={dropdownRef}
                className="absolute top-full left-0 mt-2 w-48 bg-white rounded-tile shadow-tile-lg border-2 border-quip-navy border-opacity-10 z-[70] slide-up-enter"
              >
                <div className="py-2">
                  <button
                    onClick={() => handleNavigate('/dashboard')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-teal hover:bg-quip-cream transition-colors"
                  >
                    <HomeIcon className="h-5 w-5" />
                    <span className="font-semibold">Dashboard</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/statistics')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_completed.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Statistics</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/leaderboard')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_leaderboard.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Leaderboard</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/results')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_results.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Results</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/tracking')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_prompt.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Tracking</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/completed')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_completed.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Review</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/quests')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <TreasureChestIcon className="h-5 w-5" isAvailable={true} />
                    <span className="font-semibold">Quests</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/online-users')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <img src="/icon_online_users.svg" alt="" className="h-5 w-5" />
                    <span className="font-semibold">Lobby</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/survey')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <SurveyIcon className="h-5 w-5" />
                    <span className="font-semibold">Survey</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/settings')}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                  >
                    <CogIcon className="h-5 w-5" />
                    <span className="font-semibold">Settings</span>
                  </button>
                  {player?.is_admin && (
                    <button
                      onClick={() => handleNavigate('/admin')}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-navy hover:bg-quip-cream transition-colors"
                    >
                      <CogIcon className="h-5 w-5" />
                      <span className="font-semibold">Admin</span>
                    </button>
                  )}
                  <div className="border-t border-quip-navy border-opacity-10 my-2"></div>
                  <button
                    onClick={() => {
                      setShowDropdown(false);
                      handleLogoutClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-quip-teal hover:bg-quip-cream transition-colors"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    <span className="font-semibold">Logout</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Center: Username (clickable to statistics) */}
          <div className="flex-1 text-center">
            <button
              onClick={goToStatistics}
              className="text-lg md:text-2xl text-quip-turquoise font-semibold hover:text-quip-teal transition-colors"
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
              <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 md:h-9 md:w-9" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
