// Debug logging utility for development
export const isDev = import.meta.env.DEV;

// Log levels for different types of messages
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogConfig {
  component?: string;
  level?: LogLevel;
  productionEnabled?: boolean;
}

// Default production logging configuration
const PRODUCTION_LOG_CONFIG = {
  // Only log errors and warnings in production
  enabledLevels: ['error', 'warn'] as LogLevel[],
  // Components that should log in production (critical systems)
  enabledComponents: ['GameContext', 'apiClient'] as string[],
};

export const createLogger = (defaultComponent?: string) => {
  return {
    debug: (message: string, data?: any, config?: LogConfig) => {
      log('debug', message, data, { component: defaultComponent, ...config });
    },
    info: (message: string, data?: any, config?: LogConfig) => {
      log('info', message, data, { component: defaultComponent, ...config });
    },
    warn: (message: string, data?: any, config?: LogConfig) => {
      log('warn', message, data, { component: defaultComponent, ...config });
    },
    error: (message: string, data?: any, config?: LogConfig) => {
      log('error', message, data, { component: defaultComponent, productionEnabled: true, ...config });
    },
  };
};

const log = (
  level: LogLevel,
  message: string,
  data?: any,
  config: LogConfig = {}
) => {
  const { component, productionEnabled = false } = config;

  // In development, log everything
  if (isDev) {
    const prefix = component ? `[${component}]` : '';
    const logMethod = level === 'error' ? console.error : 
                     level === 'warn' ? console.warn : 
                     console.log;
    
    logMethod(`${prefix} ${message}`, data || '');
    return;
  }

  // In production, only log if explicitly enabled
  if (!productionEnabled && !PRODUCTION_LOG_CONFIG.enabledLevels.includes(level)) {
    return;
  }

  if (component && !PRODUCTION_LOG_CONFIG.enabledComponents.includes(component) && !productionEnabled) {
    return;
  }

  // Production logging (minimal)
  const prefix = component ? `[${component}]` : '';
  if (level === 'error') {
    console.error(`${prefix} ${message}`, data || '');
  } else if (level === 'warn') {
    console.warn(`${prefix} ${message}`, data || '');
  }
};

// Legacy compatibility function
export const devLog = (component: string, message: string, data?: any) => {
  log('debug', message, data, { component });
};

// Quick access loggers for common components
export const dashboardLogger = createLogger('Dashboard');
export const gameContextLogger = createLogger('GameContext');
export const promptRoundLogger = createLogger('PromptRound');
export const copyRoundLogger = createLogger('CopyRound');
export const voteRoundLogger = createLogger('VoteRound');
export const landingLogger = createLogger('Landing');
export const questsLogger = createLogger('Quests');
export const resultsLogger = createLogger('Results');
export const trackingLogger = createLogger('Tracking');
export const statisticsLogger = createLogger('Statistics');
export const leaderboardLogger = createLogger('Leaderboard');
export const settingsLogger = createLogger('Settings');
export const adminLogger = createLogger('Admin');
export const loadingSpinnerLogger = createLogger('LoadingSpinner');
export const apiLogger = createLogger('API');
export const tutorialLogger = createLogger('Tutorial');

export default createLogger;