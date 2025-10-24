// Centralized error message localization for better UX
export interface ErrorContext {
  action?: string;
  component?: string;
  retryable?: boolean;
  suggestion?: string;
}

export const errorMessages = {
  // Network and connection errors
  network: {
    offline: "You're currently offline. Your actions will be saved and synced when you're back online.",
    timeout: "The request took too long. Please check your connection and try again.",
    connectionLost: "Connection lost. Reconnecting...",
    serverUnavailable: "Our servers are temporarily busy. Please try again in a moment.",
    rateLimited: "Too many requests. Please wait a moment before trying again.",
  },

  // Authentication errors
  auth: {
    sessionExpired: "Your session has expired. Please log in again to continue playing.",
    invalidCredentials: "Username or password is incorrect. Please double-check and try again.",
    loginRequired: "Please log in to continue playing Quipflip.",
    tokenInvalid: "Your session is no longer valid. Please log in again.",
    refreshFailed: "Unable to refresh your session. Please log in again.",
  },

  // Game-specific errors
  game: {
    roundExpired: "This round has expired. Don't worry - you can start a new one right away!",
    alreadySubmitted: "You've already submitted for this round. Check your dashboard for results!",
    insufficientBalance: "Not enough coins for this round. Claim your daily bonus or complete more rounds to earn coins.",
    noPromptsAvailable: "No prompts are available for copy rounds right now. Try creating a prompt round first!",
    noPhrasesets: "No phrase sets are available for voting. Try creating some prompts or copies first!",
    maxOutstandingPrompts: "You have too many active prompts. Wait for some to complete before creating new ones.",
    invalidPhrase: "That phrase isn't valid. Please try a different word or phrase.",
    duplicatePhrase: "That phrase has already been used. Try something more creative!",
    wordNotFound: "That word isn't in our dictionary. Please try a different word.",
    phraseTooLong: "Your phrase is too long. Keep it to 1-5 words (4-100 characters).",
    phraseTooShort: "Your phrase is too short. Please enter at least 2 characters.",
    invalidCharacters: "Please use only letters A-Z and spaces in your phrase.",
  },

  // Account and registration errors
  account: {
    emailTaken: "This email is already registered. Try logging in instead, or use a different email.",
    usernameTaken: "This username is already taken. Please try a different one.",
    usernameGeneration: "We couldn't generate a unique username. Please try again or enter your own.",
    invalidEmail: "Please enter a valid email address.",
    passwordTooShort: "Password must be at least 8 characters long.",
    registrationFailed: "Account creation failed. Please try again or contact support if the problem persists.",
  },

  // Bonus and rewards errors
  rewards: {
    bonusAlreadyClaimed: "You've already claimed your daily bonus today. Come back tomorrow for more!",
    bonusNotEligible: "Daily bonus will be available tomorrow. New accounts need to wait 24 hours.",
    prizeAlreadyClaimed: "You've already claimed this prize. Check your balance!",
    prizeNotAvailable: "This prize is no longer available.",
  },

  // General fallbacks
  general: {
    somethingWrong: "Something went wrong. Please try again, and contact support if the problem continues.",
    tryAgainLater: "Please try again in a few moments.",
    checkConnection: "Please check your internet connection and try again.",
    temporaryIssue: "We're experiencing a temporary issue. Please try again shortly.",
    saveProgress: "Don't worry - your progress has been saved.",
    contactSupport: "If this problem continues, please contact support with error ID: ",
  },
};

// Context-aware error message generator
export const getContextualErrorMessage = (
  error: any,
  context: ErrorContext = {}
): {
  message: string;
  suggestion?: string;
  retryable: boolean;
  category: 'network' | 'auth' | 'game' | 'account' | 'rewards' | 'general';
} => {
  // Check for specific backend error message first
  // Backend can return errors in several formats:
  // 1. {detail: {error: 'type', message: 'specific'}} - detail is object
  // 2. {error: 'type', message: 'specific'} - top level
  // 3. {detail: 'string message'} - simple string detail
  let specificMessage: string | null = null;
  let errorType: string | null = null;

  if (error?.detail && typeof error.detail === 'object') {
    // Format 1: detail is an object with error and message
    specificMessage = error.detail.message;
    errorType = error.detail.error;
  } else if (error?.error && typeof error.error === 'string' && error?.message) {
    // Format 2: top-level error and message fields
    specificMessage = error.message;
    errorType = error.error;
  }

  const errorDetail = typeof error === 'string' ? error : error?.detail || error?.error || error?.message || '';
  const normalizedError = String(errorDetail).toLowerCase();

  // Network errors
  if (normalizedError.includes('network') || normalizedError.includes('fetch') || error?.code === 'ERR_NETWORK') {
    return {
      message: errorMessages.network.connectionLost,
      suggestion: "Check your internet connection",
      retryable: true,
      category: 'network'
    };
  }

  if (normalizedError.includes('timeout')) {
    return {
      message: errorMessages.network.timeout,
      suggestion: "Try again with a better connection",
      retryable: true,
      category: 'network'
    };
  }

  if (normalizedError.includes('rate limit') || normalizedError.includes('too many requests')) {
    return {
      message: errorMessages.network.rateLimited,
      suggestion: "Wait 30 seconds before trying again",
      retryable: true,
      category: 'network'
    };
  }

  // Authentication errors
  if (normalizedError.includes('unauthorized') || normalizedError.includes('token') || normalizedError.includes('session')) {
    return {
      message: errorMessages.auth.sessionExpired,
      suggestion: "Click here to log in again",
      retryable: false,
      category: 'auth'
    };
  }

  if (normalizedError.includes('invalid credentials') || normalizedError.includes('password')) {
    return {
      message: errorMessages.auth.invalidCredentials,
      suggestion: "Double-check your username and password",
      retryable: true,
      category: 'auth'
    };
  }

  // Game-specific errors
  if (normalizedError.includes('expired') || normalizedError.includes('round not found')) {
    return {
      message: errorMessages.game.roundExpired,
      suggestion: "Start a new round from your dashboard",
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('already submitted')) {
    return {
      message: specificMessage || errorMessages.game.alreadySubmitted,
      suggestion: "Check your dashboard for results",
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('insufficient') || normalizedError.includes('balance')) {
    return {
      message: specificMessage || errorMessages.game.insufficientBalance,
      suggestion: "Claim your daily bonus or complete more rounds",
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('no prompts available')) {
    return {
      message: errorMessages.game.noPromptsAvailable,
      suggestion: "Create a prompt round first",
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('no wordsets') || normalizedError.includes('no phrasesets')) {
    return {
      message: errorMessages.game.noPhrasesets,
      suggestion: "Create some prompts or copies first",
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('invalid_phrase') || normalizedError.includes('invalid word')) {
    return {
      message: specificMessage || errorMessages.game.invalidPhrase,
      suggestion: "Try a different word or phrase",
      retryable: true,
      category: 'game'
    };
  }

  if (normalizedError.includes('duplicate_phrase')) {
    return {
      message: specificMessage || errorMessages.game.duplicatePhrase,
      suggestion: "Think of something more unique",
      retryable: true,
      category: 'game'
    };
  }

  // Account errors
  if (normalizedError.includes('email') && normalizedError.includes('taken')) {
    return {
      message: errorMessages.account.emailTaken,
      suggestion: "Try logging in or use a different email",
      retryable: true,
      category: 'account'
    };
  }

  if (normalizedError.includes('username_generation')) {
    return {
      message: errorMessages.account.usernameGeneration,
      suggestion: "Try the suggest button or enter your own",
      retryable: true,
      category: 'account'
    };
  }

  // Bonus/rewards errors
  if (normalizedError.includes('already_claimed_today')) {
    return {
      message: errorMessages.rewards.bonusAlreadyClaimed,
      suggestion: "Come back tomorrow for your next bonus",
      retryable: false,
      category: 'rewards'
    };
  }

  if (normalizedError.includes('not_eligible')) {
    return {
      message: errorMessages.rewards.bonusNotEligible,
      suggestion: "Daily bonus will be available tomorrow",
      retryable: false,
      category: 'rewards'
    };
  }

  // Server errors
  if (error?.status >= 500) {
    return {
      message: errorMessages.network.serverUnavailable,
      suggestion: "Our team has been notified - try again in a few minutes",
      retryable: true,
      category: 'network'
    };
  }

  // Default fallback - use specific message from backend if available
  if (specificMessage && specificMessage.length > 0) {
    return {
      message: specificMessage,
      suggestion: "Please try again",
      retryable: true,
      category: 'general'
    };
  }

  return {
    message: context.component
      ? `${errorMessages.general.somethingWrong} ${context.component} isn't responding properly.`
      : errorMessages.general.somethingWrong,
    suggestion: "If this keeps happening, contact our support team",
    retryable: true,
    category: 'general'
  };
};

// Action-specific error messages
export const getActionErrorMessage = (action: string, error: any): string => {
  const contextualError = getContextualErrorMessage(error, { action });
  
  const actionMessages: Record<string, string> = {
    login: "Unable to log in",
    register: "Unable to create account",
    'start-prompt': "Unable to start prompt round",
    'start-copy': "Unable to start copy round", 
    'start-vote': "Unable to start vote round",
    'submit-phrase': "Unable to submit your phrase",
    'submit-vote': "Unable to submit your vote",
    'claim-bonus': "Unable to claim daily bonus",
    'claim-prize': "Unable to claim prize",
    'load-dashboard': "Unable to load dashboard",
    'load-tracking': "Unable to load your past rounds",
  };

  const actionMessage = actionMessages[action] || `Unable to ${action}`;
  return `${actionMessage}. ${contextualError.message}`;
};