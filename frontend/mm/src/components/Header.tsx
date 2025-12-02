import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useNavigationHistory } from '../contexts/NavigationHistoryContext';
import { useTutorial } from '../contexts/TutorialContext';
import { useHeaderIndicators } from '../hooks/useHeaderIndicators';
import { useNetwork } from '../contexts/NetworkContext';
import { Header as SharedHeader, type HeaderMenuItem } from '@crowdcraft';
import { TreasureChestIcon } from '@crowdcraft/components/icons/TreasureChestIcon.tsx';
import {
  AdminIcon,
  HomeIcon,
  LeaderboardIcon,
  LobbyIcon,
  CircleIcon,
  SettingsIcon,
  StatisticsIcon,
  SurveyIcon,
} from '@crowdcraft/components/icons/NavigationIcons.tsx';
import { QuestionMarkIcon, ResultsIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { hasCompletedSurvey } from '@crowdcraft/utils/betaSurvey.ts';
import { apiClient } from '@/api/client';
import { componentLogger } from '@crowdcraft/utils/logger.ts';
import GuestLogoutWarning from '@crowdcraft/components/GuestLogoutWarning.tsx';

export const Header: React.FC = () => {
  const { state, actions } = useGame();
  const { player, username } = state;
  const { logout, refreshDashboard, refreshBalance } = actions;
  const navigate = useNavigate();
  const location = useLocation();
  const { goBack } = useNavigationHistory();
  const {
    state: { status: tutorialStatus },
  } = useTutorial();
  const { unviewedCount } = useHeaderIndicators();
  const { isOffline } = useNetwork();

  const [showGuestLogoutWarning, setShowGuestLogoutWarning] = React.useState(false);
  const [guestCredentials, setGuestCredentials] = React.useState<{ email: string | null; password: string | null } | null>(null);
  const [surveyCompleted, setSurveyCompleted] = React.useState(false);

  const showBackArrow = location.pathname !== '/dashboard';

  React.useEffect(() => {
    const checkSurveyStatus = async () => {
      if (!player?.player_id) return;

      try {
        const cacheKey = `beta_survey_status_${player.player_id}`;
        const now = Date.now();

        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const { data, timestamp } = JSON.parse(cached);
            if (now - timestamp < 300000) {
              const completedLocal = hasCompletedSurvey(player.player_id);
              setSurveyCompleted(completedLocal || data.has_submitted);
              return;
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

        localStorage.setItem(cacheKey, JSON.stringify({
          data: status,
          timestamp: now,
        }));

        setSurveyCompleted(status.has_submitted);
      } catch (err) {
        componentLogger.warn('Failed to check survey status:', err);
      }
    };

    checkSurveyStatus();
  }, [player?.player_id]);

  const handleBackArrowClick = React.useCallback(async () => {
    try {
      await Promise.all([refreshDashboard(), refreshBalance()]);
    } catch (err) {
      componentLogger.warn('Failed to refresh from header icon:', err);
    }

    goBack();
  }, [refreshDashboard, refreshBalance, goBack]);

  const handleLogoutClick = React.useCallback(() => {
    if (!player?.is_guest) {
      logout();
      return;
    }

    let email: string | null = player?.email ?? null;
    let password: string | null = null;

    if (typeof window !== 'undefined') {
      try {
        const stored = window.localStorage.getItem('crowdcraft_guest_credentials');
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

  const handleNavigate = React.useCallback(
    (path: string) => {
      navigate(path);
    },
    [navigate],
  );

  if (!player) {
    return null;
  }

  const showTutorialInMenu = player.is_guest || tutorialStatus?.completed === false;

  const primaryMenuItems: HeaderMenuItem[] = [
    { key: 'dashboard', label: 'Dashboard', icon: HomeIcon, onClick: () => handleNavigate('/dashboard'), variant: 'accent' },
    { key: 'statistics', label: 'Statistics', icon: StatisticsIcon, onClick: () => handleNavigate('/statistics') },
    { key: 'leaderboard', label: 'Leaderboard', icon: LeaderboardIcon, onClick: () => handleNavigate('/leaderboard') },
    {
      key: 'results',
      label: 'Results',
      icon: ResultsIcon,
      iconProps: { variant: unviewedCount > 0 ? 'orange' : 'teal' },
      onClick: () => handleNavigate('/game/results'),
    },
    {
      key: 'quests',
      label: 'Quests',
      icon: TreasureChestIcon,
      iconProps: { isAvailable: true },
      onClick: () => handleNavigate('/quests'),
    },
    { key: 'online-users', label: 'Lobby', icon: LobbyIcon, onClick: () => handleNavigate('/online-users') },
    { key: 'circles', label: 'Circles', icon: CircleIcon, onClick: () => handleNavigate('/circles') },
  ];

  if (showTutorialInMenu) {
    primaryMenuItems.push({
      key: 'tutorial',
      label: 'Tutorial',
      icon: QuestionMarkIcon,
      onClick: () => handleNavigate('/dashboard?startTutorial=true'),
    });
  }

  if (!surveyCompleted) {
    primaryMenuItems.push({
      key: 'survey',
      label: 'Survey',
      icon: SurveyIcon,
      onClick: () => handleNavigate('/survey/beta'),
    });
  }

  const footerItems: HeaderMenuItem[] = [
    { key: 'settings', label: 'Settings', icon: SettingsIcon, onClick: () => handleNavigate('/settings') },
  ];

  if (player?.is_admin) {
    footerItems.push({ key: 'admin', label: 'Admin', icon: AdminIcon, onClick: () => handleNavigate('/admin') });
  }

  return (
    <SharedHeader
      logoSrc="/menu.png"
      logoAlt="MemeMint"
      playerName={player.username || username || ''}
      wallet={player.wallet}
      vault={player.vault}
      isGuest={Boolean(player.is_guest)}
      isOffline={isOffline}
      showBackArrow={showBackArrow}
      onBackClick={handleBackArrowClick}
      onStatisticsClick={() => navigate('/statistics')}
      onLogoutClick={handleLogoutClick}
      dropdownSections={[primaryMenuItems]}
      footerItems={footerItems}
      renderGuestLogoutWarning={(
        <GuestLogoutWarning
          isVisible={showGuestLogoutWarning}
          username={player.username || username}
          guestCredentials={guestCredentials}
          onConfirmLogout={handleConfirmGuestLogout}
          onDismiss={handleDismissGuestLogout}
        />
      )}
      logoTitle="Open menu"
      backTitle="Go back (refresh)"
    />
  );
};
