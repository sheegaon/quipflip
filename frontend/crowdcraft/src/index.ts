// Components
export { BalanceFlipper } from './components/BalanceFlipper';
export { Pagination } from './components/Pagination';
export { default as NewUserWelcomeOverlay } from './components/NewUserWelcomeOverlay';
export { Timer } from './components/Timer';
export { ProgressBar } from './components/ProgressBar';
export { StatusBadge } from './components/StatusBadge';
export { default as CurrencyDisplay } from './components/CurrencyDisplay';
export { ErrorBoundary } from './components/ErrorBoundary';
export { AppErrorFallback, PageErrorFallback } from './components/ErrorFallback';
export { default as SuccessNotification } from './components/SuccessNotification';
export { default as NotificationDisplay } from './components/NotificationDisplay';
export { default as NotificationToast } from './components/NotificationToast';
export { default as PingNotificationDisplay } from './components/PingNotificationDisplay';
export { default as ThumbFeedbackButton } from './components/ThumbFeedbackButton';
export { default as EditableConfigField } from './components/EditableConfigField';

// Icons
export * from './components/icons/ArrowIcons';
export * from './components/icons/EngagementIcons';
export * from './components/icons/NavigationIcons';
export * from './components/icons/QuestIcons';
export * from './components/icons/RoundIcons';
export * from './components/icons/StateIcons';
export * from './components/icons/TreasureChestIcon';

// Config
export * from './config/phraseValidation'
export * from './config/tutorialSteps'

// Hooks
export * from './hooks/useExponentialBackoff'
export * from './hooks/useNetworkStatus'
export * from './hooks/useOfflineCache'
export * from './hooks/usePhraseValidation'
export * from './hooks/usePracticePhraseset'
export * from './hooks/usePracticePhrasesetSession'
export * from './hooks/useTimer'
export * from './hooks/useWebSocket'
export * from './utils'
export { BaseApiClient, extractErrorMessage, clearStoredCredentials } from './api/BaseApiClient'

// Contexts
export * from './contexts/NavigationHistoryContext'
export * from './contexts/NotificationContext'
export * from './contexts/TutorialContext'
export * from './contexts/QuestContext'
export * from './contexts/ResultsContext'

// Types
export * from './types/errors'

// Statistics Components - using default exports
export { default as EarningsChart } from './components/statistics/EarningsChart';
export { default as FrequencyChart } from './components/statistics/FrequencyChart';
export { default as HistoricalTrendsChart } from './components/statistics/HistoricalTrendsChart';
export { default as SpendingChart } from './components/statistics/SpendingChart';
export { default as WeeklyLeaderboard } from './components/statistics/WeeklyLeaderboard';
export { default as WinRateChart } from './components/statistics/WinRateChart';
