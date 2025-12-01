import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useNavigationHistory } from '../contexts/NavigationHistoryContext';
import { useTutorial } from '../contexts/TutorialContext';
import { useHeaderIndicators } from '../hooks/useHeaderIndicators';
import { useNetwork } from '../contexts/NetworkContext';
import { BalanceFlipper } from '../../../crowdcraft/src/components/BalanceFlipper.tsx';
import { TreasureChestIcon } from '../../../crowdcraft/src/components/icons/TreasureChestIcon.tsx';
import { ArrowLeftIcon } from '../../../crowdcraft/src/components/icons/ArrowIcons.tsx';
import {
  AdminIcon,
  HomeIcon,
  LeaderboardIcon,
  LobbyIcon,
  CircleIcon,
  SettingsIcon,
  StatisticsIcon,
  SurveyIcon,
} from '../../../crowdcraft/src/components/icons/NavigationIcons.tsx';
import { QuestionMarkIcon, ResultsIcon } from '../../../crowdcraft/src/components/icons/EngagementIcons.tsx';
import { hasCompletedSurvey } from '../utils/betaSurvey';
import { apiClient } from '../api/client';
import { componentLogger } from '../utils/logger';
import GuestLogoutWarning from './GuestLogoutWarning';

export const Header: React.FC = () => {
  const { state, actions } = useGame();
  const { player, username } = state;
  const { logout, refreshDashboard, refreshBalance } = actions;
  const navigate = useNavigate();
  const location = useLocation();
  const { goBack } = useNavigationHistory();
  const { status: tutorialStatus } = useTutorial();
  const { unviewedCount } = useHeaderIndicators();
  const { isOffline } = useNetwork();

  const [showGuestLogoutWarning, setShowGuestLogoutWarning] = React.useState(false);
  const [guestCredentials, setGuestCredentials] = React.useState<{ email: string | null; password: string | null } | null>(null);
  const [showDropdown, setShowDropdown] = React.useState(false);
  const [surveyCompleted, setSurveyCompleted] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const logoButtonRef = React.useRef<HTMLButtonElement>(null);

  // Show back arrow on all pages except dashboard
  const showBackArrow = location.pathname !== '/dashboard';

  // Check survey completion status
  React.useEffect(() => {
    const checkSurveyStatus = async () => {
      if (!player?.player_id) return;

      try {
        // Cache key for this player's survey status
        const cacheKey = `beta_survey_status_${player.player_id}`;
        const now = Date.now();
        
        // Check if we have cached data less than 5 minutes old
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const { data, timestamp } = JSON.parse(cached);
            if (now - timestamp < 300000) { // 5 minutes = 300000ms
              const completedLocal = hasCompletedSurvey(player.player_id);
              setSurveyCompleted(completedLocal || data.has_submitted);
              return; // Use cached data
            }
          } catch {
            // Invalid cache, continue to fetch
          }
        }

        const completedLocal = hasCompletedSurvey(player.player_id);
        if (completedLocal) {
          setSurveyCompleted(true);
          return;
        }

        const status = await apiClient.getBetaSurveyStatus();
        
        // Cache the result for 5 minutes
        localStorage.setItem(cacheKey, JSON.stringify({
          data: status,
          timestamp: now
        }));
        
        setSurveyCompleted(status.has_submitted);
      } catch (err) {
        componentLogger.warn('Failed to check survey status:', err);
      }
    };

    checkSurveyStatus();
  }, [player?.player_id]);

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
      componentLogger.warn('Failed to refresh from header icon:', err);
    }

    goBack();
  }, [refreshDashboard, refreshBalance, goBack]);

  const logoTitle = 'Open menu';
  const backArrowTitle = 'Go back (refresh)';

  const handleLogoutClick = React.useCallback(() => {
    if (!player?.is_guest) {
      logout();
      return;
    }

    let email: string | null = player?.email ?? null;
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
        componentLogger.warn('Failed to read guest credentials from storage', err);
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
      const target = event.target as Node;
      // Don't close if clicking on the logo button or inside the dropdown
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(target) &&
        logoButtonRef.current &&
        !logoButtonRef.current.contains(target)
      ) {
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

  if (!player) {
    return null;
  }

  // Determine if tutorial should be shown in menu
  // Always show for guests, show for logged-in users only if not completed
  const showTutorialInMenu = player.is_guest || !tutorialStatus?.completed;

  return (
    <>
      <GuestLogoutWarning
        isVisible={showGuestLogoutWarning}
        username={player.username || username}
        guestCredentials={guestCredentials}
        onConfirmLogout={handleConfirmGuestLogout}
        onDismiss={handleDismissGuestLogout}
      />
      <div className="bg-ccl-warm-ivory shadow-tile-sm relative z-50">
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
                <ArrowLeftIcon className="w-7 h-7 md:w-9 md:h-9" aria-hidden="true" />
              </button>
            )}
            <button
              ref={logoButtonRef}
              type="button"
              onClick={handleLogoClick}
              className="cursor-pointer transition-opacity hover:opacity-90"
              title={logoTitle}
              aria-label={logoTitle}
            >
              <img src="/menu.png" alt="MemeMint" className="md:h-10 h-8 w-auto" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div
                ref={dropdownRef}
                className="absolute top-full left-0 mt-2 w-48 bg-white rounded-tile shadow-tile-lg border-2 border-ccl-navy border-opacity-10 z-[100] slide-up-enter"
              >
                <div className="py-2">
                  <button
                    onClick={() => handleNavigate('/dashboard')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-teal hover:bg-ccl-cream transition-colors"
                  >
                    <HomeIcon className="h-5 w-5" />
                    <span className="font-semibold">Dashboard</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/statistics')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <StatisticsIcon className="h-5 w-5" />
                    <span className="font-semibold">Statistics</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/leaderboard')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <LeaderboardIcon className="h-5 w-5" />
                    <span className="font-semibold">Leaderboard</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/game/results')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <ResultsIcon
                      className="h-5 w-5"
                      variant={unviewedCount > 0 ? 'orange' : 'teal'}
                    />
                    <span className="font-semibold">Results</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/quests')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <TreasureChestIcon className="h-5 w-5" isAvailable={true} />
                    <span className="font-semibold">Quests</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/online-users')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <LobbyIcon className="h-5 w-5" />
                    <span className="font-semibold">Lobby</span>
                  </button>
                  <button
                    onClick={() => handleNavigate('/circles')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <CircleIcon className="h-5 w-5" />
                    <span className="font-semibold">Circles</span>
                  </button>
                  {showTutorialInMenu && (
                    <button
                      onClick={() => handleNavigate('/dashboard?startTutorial=true')}
                      className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                    >
                      <QuestionMarkIcon className="h-5 w-5" />
                      <span className="font-semibold">Tutorial</span>
                    </button>
                  )}
                  {!surveyCompleted && (
                    <button
                      onClick={() => handleNavigate('/survey/beta')}
                      className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                    >
                      <SurveyIcon className="h-5 w-5" />
                      <span className="font-semibold">Survey</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleNavigate('/settings')}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                  >
                    <SettingsIcon className="h-5 w-5" />
                    <span className="font-semibold">Settings</span>
                  </button>
                  {player?.is_admin && (
                    <button
                      onClick={() => handleNavigate('/admin')}
                      className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-navy hover:bg-ccl-cream transition-colors"
                    >
                      <AdminIcon className="h-5 w-5" />
                      <span className="font-semibold">Admin</span>
                    </button>
                  )}
                  <div className="border-t border-ccl-navy border-opacity-10 my-2"></div>
                  <button
                    onClick={() => {
                      setShowDropdown(false);
                      handleLogoutClick();
                    }}
                    className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-teal hover:bg-ccl-cream transition-colors"
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
              className="text-md md:text-2xl text-ccl-turquoise font-semibold hover:text-ccl-teal transition-colors"
              title="View your statistics"
            >
              <div className="flex items-center justify-center gap-0.5 md:gap-3">
                {!player.is_guest && (
                  <div className="flex items-center" role="status" aria-live="polite">
                    <div
                      className={`w-2 h-2 rounded-full ${!isOffline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}
                    >
                      <span className="sr-only">{!isOffline ? 'Online' : 'Offline'}</span>
                    </div>
                  </div>
                )}
                <span>{player.username || username}</span>
              </div>
            </button>
          </div>

          {/* Right: Wallet + Vault + Logout (guest only) */}
          <div className="flex items-center gap-0.5 md:gap-4">
            {/* Wallet Balance */}
            <button
              type="button"
              onClick={goToStatistics}
              className="flex items-center gap-0.5 tutorial-balance border border-white/10 rounded-xl px-0.5 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
              title="Wallet balance"
              aria-label="Wallet balance"
            >
              <img src="/memecoin.png" alt="Wallet" className="w-5 h-5 md:w-7 md:h-7" />
              <BalanceFlipper
                value={player.wallet}
                className="text-xl md:text-2xl font-display font-bold text-ccl-turquoise"
              />
            </button>
            {/* Vault Balance */}
            <button
              type="button"
              onClick={goToStatistics}
              className="flex items-center gap-0.5 border border-white/10 rounded-xl px-0.5 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
              title="Vault balance"
              aria-label="Vault balance"
            >
              <img src="/vault.png" alt="Vault" className="w-5 h-5 md:w-7 md:h-7" />
              <BalanceFlipper
                value={player.vault}
                className="text-xl md:text-2xl font-display font-bold text-ccl-turquoise"
              />
            </button>
            {/* Logout Button - Only visible for guests */}
            {player.is_guest && (
              <button onClick={handleLogoutClick} className="text-ccl-teal hover:text-ccl-turquoise" title="Logout">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 md:h-9 md:w-9" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
    </>
  );
};
