// Centralized error message localization for better UX

export interface ErrorContext {
  action?: string;
  component?: string;
  retryable?: boolean;
  suggestion?: string;
}

export const errorMessages = {
  network: {
    offline: "You're currently offline. Your actions will be saved and synced when you're back online.",
    timeout: 'The request took too long. Please check your connection and try again.',
    connectionLost: 'Connection lost. Reconnecting...',
    serverUnavailable: 'Our servers are temporarily busy. Please try again in a moment.',
    rateLimited: 'Too many requests. Please wait a moment before trying again.',
  },
  auth: {
    sessionExpired: 'Your session has expired. Please log in again to continue playing.',
    invalidCredentials: 'Username or password is incorrect. Please double-check and try again.',
    loginRequired: 'Please log in to continue playing Initial Reaction.',
    tokenInvalid: 'Your session is no longer valid. Please log in again.',
    refreshFailed: 'Unable to refresh your session. Please log in again.',
  },
  game: {
    roundExpired: 'This battle has expired. Start a new one to keep playing!',
    alreadySubmitted: "You've already submitted for this battle. Check your dashboard for results!",
    insufficientBalance: 'Not enough InitCoins for this round. Claim your daily bonus or win more rounds to earn coins.',
    noPromptsAvailable: 'No prompts are available right now. Try again in a moment!',
    noPhrasesets: 'No sets are available right now. Try creating or joining a battle first.',
    invalidPhrase: 'That entry is not valid. Please try a different word.',
    duplicatePhrase: 'That entry has already been used. Try something more creative!',
    wordNotFound: "That word isn't in our dictionary. Please try a different word.",
    phraseTooLong: 'Your entry is too long. Keep it concise.',
    phraseTooShort: 'Your entry is too short. Please enter at least 2 characters.',
    invalidCharacters: 'Please use only letters A-Z in your entry.',
    playerLocked: 'Your account is temporarily locked. Please try again later.',
  },
  account: {
    emailTaken: 'This email is already registered. Try logging in instead, or use a different email.',
    usernameTaken: 'This username is already taken. Please try a different one.',
    usernameGeneration: "We couldn't generate a unique username. Please try again or enter your own.",
    invalidEmail: 'Please enter a valid email address.',
    passwordTooShort: 'Password must be at least 8 characters long.',
    registrationFailed: 'Account creation failed. Please try again or contact support if the problem persists.',
  },
  rewards: {
    bonusAlreadyClaimed: "You've already claimed your daily bonus today. Come back tomorrow for more!",
    bonusNotEligible: 'Daily bonus will be available tomorrow. New accounts need to wait 24 hours.',
    prizeAlreadyClaimed: "You've already claimed this prize. Check your wallet!",
    prizeNotAvailable: 'This prize is no longer available.',
  },
  general: {
    somethingWrong: 'Something went wrong. Please try again, and contact support if the problem continues.',
    tryAgainLater: 'Please try again in a few moments.',
    checkConnection: 'Please check your internet connection and try again.',
    temporaryIssue: "We're experiencing a temporary issue. Please try again shortly.",
    saveProgress: 'Your progress has been saved.',
    contactSupport: 'If this problem continues, please contact support with error ID: ',
  },
};

export const getContextualErrorMessage = (
  error: unknown,
  context: ErrorContext = {}
): {
  message: string;
  suggestion?: string;
  retryable: boolean;
  category: 'network' | 'auth' | 'game' | 'account' | 'rewards' | 'general';
} => {
  let specificMessage: string | null = null;

  if (
    typeof error === 'object' &&
    error !== null &&
    'detail' in error &&
    typeof (error as Record<string, unknown>).detail === 'object' &&
    (error as Record<string, unknown>).detail !== null &&
    'message' in ((error as Record<string, unknown>).detail as object)
  ) {
    specificMessage = ((error as Record<string, unknown>).detail as Record<string, unknown>).message as string;
  } else if (
    typeof error === 'object' &&
    error !== null &&
    'error' in error &&
    typeof (error as Record<string, unknown>).error === 'string' &&
    'message' in error
  ) {
    specificMessage = (error as Record<string, unknown>).message as string;
  }

  let errorDetail: unknown;
  if (typeof error === 'string') {
    errorDetail = error;
  } else if (typeof error === 'object' && error !== null) {
    const errorObj = error as Record<string, unknown>;
    errorDetail = errorObj.detail || errorObj.error || errorObj.message || '';
  } else {
    errorDetail = '';
  }
  const normalizedError = String(errorDetail).toLowerCase();

  const hasNetworkErrorCode =
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    (error as Record<string, unknown>).code === 'ERR_NETWORK';

  if (normalizedError.includes('network') || normalizedError.includes('fetch') || hasNetworkErrorCode) {
    return {
      message: errorMessages.network.connectionLost,
      suggestion: 'Check your internet connection',
      retryable: true,
      category: 'network'
    };
  }

  if (normalizedError.includes('timeout')) {
    return {
      message: errorMessages.network.timeout,
      suggestion: 'Try again with a better connection',
      retryable: true,
      category: 'network'
    };
  }

  if (normalizedError.includes('rate limit') || normalizedError.includes('too many requests')) {
    return {
      message: errorMessages.network.rateLimited,
      suggestion: 'Wait 30 seconds before trying again',
      retryable: true,
      category: 'network'
    };
  }

  if (normalizedError.includes('unauthorized') || normalizedError.includes('token') || normalizedError.includes('session')) {
    return {
      message: errorMessages.auth.sessionExpired,
      suggestion: 'Click here to log in again',
      retryable: false,
      category: 'auth'
    };
  }

  const hasStatus422 =
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    (error as Record<string, unknown>).status === 422;

  if (hasStatus422 && normalizedError.includes('password must')) {
    return {
      message: String(errorDetail),
      suggestion: 'Please check password requirements',
      retryable: true,
      category: 'account'
    };
  }

  if (normalizedError.includes('invalid credentials') || (normalizedError.includes('password') && !normalizedError.includes('password must'))) {
    return {
      message: errorMessages.auth.invalidCredentials,
      suggestion: 'Double-check your username and password',
      retryable: true,
      category: 'auth'
    };
  }

  if (normalizedError.includes('expired') || normalizedError.includes('round not found')) {
    return {
      message: errorMessages.game.roundExpired,
      suggestion: 'Start a new battle from your dashboard',
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('already submitted')) {
    return {
      message: specificMessage || errorMessages.game.alreadySubmitted,
      suggestion: 'Check your dashboard for results',
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('insufficient') || normalizedError.includes('balance')) {
    return {
      message: specificMessage || errorMessages.game.insufficientBalance,
      suggestion: 'Claim your daily bonus or complete more rounds',
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('player_locked')) {
    return {
      message: errorMessages.game.playerLocked,
      suggestion: 'Thanks for your patience while we review things.',
      retryable: false,
      category: 'game'
    };
  }

  if (normalizedError.includes('invalid_phrase') || normalizedError.includes('invalid word')) {
    return {
      message: specificMessage || errorMessages.game.invalidPhrase,
      suggestion: 'Try a different word',
      retryable: true,
      category: 'game'
    };
  }

  if (normalizedError.includes('duplicate_phrase')) {
    return {
      message: specificMessage || errorMessages.game.duplicatePhrase,
      suggestion: 'Try something more unique',
      retryable: true,
      category: 'game'
    };
  }

  if (normalizedError.includes('email') && normalizedError.includes('taken')) {
    return {
      message: errorMessages.account.emailTaken,
      suggestion: 'Try logging in or use a different email',
      retryable: true,
      category: 'account'
    };
  }

  if (normalizedError.includes('username_generation')) {
    return {
      message: errorMessages.account.usernameGeneration,
      suggestion: 'Try the suggest button or enter your own',
      retryable: true,
      category: 'account'
    };
  }

  if (normalizedError.includes('already_claimed_today')) {
    return {
      message: errorMessages.rewards.bonusAlreadyClaimed,
      suggestion: 'Come back tomorrow for your next bonus',
      retryable: false,
      category: 'rewards'
    };
  }

  if (normalizedError.includes('not_eligible')) {
    return {
      message: errorMessages.rewards.bonusNotEligible,
      suggestion: 'Daily bonus will be available tomorrow',
      retryable: false,
      category: 'rewards'
    };
  }

  if (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    typeof (error as Record<string, unknown>).status === 'number' &&
    ((error as Record<string, unknown>).status as number) >= 500
  ) {
    return {
      message: errorMessages.network.serverUnavailable,
      suggestion: 'Our team has been notified - try again in a few minutes',
      retryable: true,
      category: 'network'
    };
  }

  if (specificMessage && specificMessage.length > 0) {
    return {
      message: specificMessage,
      suggestion: 'Please try again',
      retryable: true,
      category: 'general'
    };
  }

  return {
    message: context.component
      ? `${errorMessages.general.somethingWrong} ${context.component} isn't responding properly.`
      : errorMessages.general.somethingWrong,
    suggestion: 'If this keeps happening, contact our support team',
    retryable: true,
    category: 'general'
  };
};

export const getActionErrorMessage = (action: string, error: unknown): string => {
  const contextualError = getContextualErrorMessage(error, { action });

  const actionMessages: Record<string, string> = {
    login: 'Unable to log in',
    register: 'Unable to create account',
    'login-guest': 'Unable to start a guest session',
    'upgrade-account': 'Unable to upgrade account',
    'start-battle': 'Unable to start your battle',
    'submit-backronym': 'Unable to submit your backronym',
    'validate-backronym': 'Unable to validate your backronym',
    'submit-vote': 'Unable to submit your vote',
    'claim-bonus': 'Unable to claim daily bonus',
    'load-dashboard': 'Unable to load dashboard',
    'check-set-status': 'Unable to load battle status',
  };

  const actionMessage = actionMessages[action] || `Unable to ${action}`;
  return `${actionMessage}. ${contextualError.message}`;
};
