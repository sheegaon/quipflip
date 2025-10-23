import React from 'react';

// Smart polling manager that adapts intervals based on user activity and network conditions
export interface PollConfig {
  key: string;
  interval: number;
  maxInterval?: number;
  backoffMultiplier?: number;
  immediateOnFocus?: boolean;
  pauseWhenInactive?: boolean;
  retryOnError?: boolean;
  maxRetries?: number;
}

export interface PollState {
  isPolling: boolean;
  currentInterval: number;
  errorCount: number;
  lastSuccessTime: number;
  lastErrorTime: number;
}

class SmartPollingManager {
  private polls: Map<string, {
    config: PollConfig;
    state: PollState;
    timeoutId?: number;
    callback: () => Promise<void>;
    abortController?: AbortController;
  }> = new Map();

  private isUserActive = true;
  private isOnline = navigator.onLine;
  private focusTime = Date.now();

  constructor() {
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Track user activity
    const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    activityEvents.forEach(event => {
      document.addEventListener(event, this.handleUserActivity, { passive: true });
    });

    // Track focus/visibility
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
    window.addEventListener('focus', this.handleWindowFocus);
    window.addEventListener('blur', this.handleWindowBlur);

    // Track network status
    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);

    // Cleanup on beforeunload
    window.addEventListener('beforeunload', this.cleanup);
  }

  private handleUserActivity = () => {
    this.isUserActive = true;
    this.focusTime = Date.now();
  };

  private handleVisibilityChange = () => {
    if (!document.hidden) {
      this.isUserActive = true;
      this.focusTime = Date.now();
      // Trigger immediate polls for active polls when page becomes visible
      this.polls.forEach((poll, key) => {
        if (poll.config.immediateOnFocus && poll.state.isPolling) {
          this.executePoll(key);
        }
      });
    }
  };

  private handleWindowFocus = () => {
    this.isUserActive = true;
    this.focusTime = Date.now();
  };

  private handleWindowBlur = () => {
    // Mark as inactive after 5 seconds of no activity
    setTimeout(() => {
      const timeSinceActivity = Date.now() - this.focusTime;
      if (timeSinceActivity >= 5000) {
        this.isUserActive = false;
      }
    }, 5000);
  };

  private handleOnline = () => {
    this.isOnline = true;
    // Resume all paused polls when coming back online
    this.polls.forEach((poll, key) => {
      if (poll.state.isPolling) {
        this.schedulePoll(key);
      }
    });
  };

  private handleOffline = () => {
    this.isOnline = false;
    // Cancel all pending polls when going offline
    this.polls.forEach(poll => {
      if (poll.timeoutId) {
        clearTimeout(poll.timeoutId);
        poll.timeoutId = undefined;
      }
      if (poll.abortController) {
        poll.abortController.abort();
      }
    });
  };

  private getEffectiveInterval(key: string): number {
    const poll = this.polls.get(key);
    if (!poll) return 60000;

    const { config, state } = poll;
    let interval = state.currentInterval;

    // Reduce frequency when user is inactive
    if (!this.isUserActive && config.pauseWhenInactive) {
      interval = Math.max(interval * 2, 120000); // At least 2 minutes when inactive
    }

    // Increase interval after errors with exponential backoff
    if (state.errorCount > 0 && config.backoffMultiplier) {
      const backoffFactor = Math.pow(config.backoffMultiplier, Math.min(state.errorCount, 5));
      interval = Math.min(interval * backoffFactor, config.maxInterval || 300000);
    }

    // Don't poll if offline
    if (!this.isOnline) {
      return 0;
    }

    return interval;
  }

  private async executePoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll || !poll.state.isPolling) return;

    // Cancel any pending timeout
    if (poll.timeoutId) {
      clearTimeout(poll.timeoutId);
      poll.timeoutId = undefined;
    }

    // Create abort controller for this poll
    poll.abortController = new AbortController();

    try {
      await poll.callback();
      
      // Success - reset error count and interval
      poll.state.errorCount = 0;
      poll.state.currentInterval = poll.config.interval;
      poll.state.lastSuccessTime = Date.now();
      
      // Schedule next poll
      this.schedulePoll(key);
    } catch (error) {
      // Error handling
      poll.state.errorCount++;
      poll.state.lastErrorTime = Date.now();

      if (poll.config.retryOnError && poll.state.errorCount <= (poll.config.maxRetries || 3)) {
        // Retry with backoff
        this.schedulePoll(key);
      } else if (!poll.config.retryOnError) {
        // Continue polling even after errors, but with increased interval
        this.schedulePoll(key);
      } else {
        // Stop polling after max retries
        this.stopPoll(key);
      }
    }
  }

  private schedulePoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll || !poll.state.isPolling) return;

    const interval = this.getEffectiveInterval(key);
    
    if (interval > 0) {
      poll.timeoutId = window.setTimeout(() => {
        this.executePoll(key);
      }, interval);
    }
  }

  startPoll(config: PollConfig, callback: () => Promise<void>) {
    // Stop existing poll if any
    this.stopPoll(config.key);

    const state: PollState = {
      isPolling: true,
      currentInterval: config.interval,
      errorCount: 0,
      lastSuccessTime: Date.now(),
      lastErrorTime: 0,
    };

    this.polls.set(config.key, {
      config,
      state,
      callback,
    });

    // Start immediately if online
    if (this.isOnline) {
      this.executePoll(config.key);
    }
  }

  stopPoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll) return;

    poll.state.isPolling = false;
    
    if (poll.timeoutId) {
      clearTimeout(poll.timeoutId);
      poll.timeoutId = undefined;
    }
    
    if (poll.abortController) {
      poll.abortController.abort();
    }

    this.polls.delete(key);
  }

  pausePoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll) return;

    poll.state.isPolling = false;
    
    if (poll.timeoutId) {
      clearTimeout(poll.timeoutId);
      poll.timeoutId = undefined;
    }
  }

  resumePoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll) return;

    poll.state.isPolling = true;
    this.schedulePoll(key);
  }

  triggerImmediatePoll(key: string) {
    const poll = this.polls.get(key);
    if (!poll || !poll.state.isPolling) return;

    this.executePoll(key);
  }

  getPollState(key: string): PollState | undefined {
    return this.polls.get(key)?.state;
  }

  getAllPollStates(): Record<string, PollState> {
    const states: Record<string, PollState> = {};
    this.polls.forEach((poll, key) => {
      states[key] = poll.state;
    });
    return states;
  }

  updatePollConfig(key: string, updates: Partial<PollConfig>) {
    const poll = this.polls.get(key);
    if (!poll) return;

    poll.config = { ...poll.config, ...updates };
    
    // Restart poll with new config if it's currently running
    if (poll.state.isPolling) {
      this.schedulePoll(key);
    }
  }

  cleanup = () => {
    this.polls.forEach((poll, key) => {
      this.stopPoll(key);
    });
    this.polls.clear();
  };
}

// Singleton instance
export const pollingManager = new SmartPollingManager();

// React hook for using smart polling
export const useSmartPolling = () => {
  const startPoll = React.useCallback((config: PollConfig, callback: () => Promise<void>) => {
    pollingManager.startPoll(config, callback);
  }, []);

  const stopPoll = React.useCallback((key: string) => {
    pollingManager.stopPoll(key);
  }, []);

  const pausePoll = React.useCallback((key: string) => {
    pollingManager.pausePoll(key);
  }, []);

  const resumePoll = React.useCallback((key: string) => {
    pollingManager.resumePoll(key);
  }, []);

  const triggerPoll = React.useCallback((key: string) => {
    pollingManager.triggerImmediatePoll(key);
  }, []);

  const getPollState = React.useCallback((key: string) => {
    return pollingManager.getPollState(key);
  }, []);

  return {
    startPoll,
    stopPoll,
    pausePoll,
    resumePoll,
    triggerPoll,
    getPollState,
  };
};

// Predefined polling configurations for common use cases
export const PollConfigs = {
  DASHBOARD: {
    key: 'dashboard',
    interval: 30000,        // 30 seconds
    maxInterval: 300000,    // 5 minutes max
    backoffMultiplier: 1.5,
    immediateOnFocus: true,
    pauseWhenInactive: true,
    retryOnError: true,
    maxRetries: 3,
  },
  ROUND_TIMER: {
    key: 'round-timer',
    interval: 5000,         // 5 seconds
    maxInterval: 15000,     // 15 seconds max
    backoffMultiplier: 1.2,
    immediateOnFocus: true,
    pauseWhenInactive: false, // Keep timer accurate
    retryOnError: true,
    maxRetries: 5,
  },
  PHRASESET_DETAILS: {
    key: 'phraseset-details',
    interval: 60000,        // 1 minute
    maxInterval: 300000,    // 5 minutes max
    backoffMultiplier: 2,
    immediateOnFocus: true,
    pauseWhenInactive: true,
    retryOnError: true,
    maxRetries: 3,
  },
  BALANCE_REFRESH: {
    key: 'balance',
    interval: 120000,       // 2 minutes
    maxInterval: 600000,    // 10 minutes max
    backoffMultiplier: 1.5,
    immediateOnFocus: false,
    pauseWhenInactive: true,
    retryOnError: true,
    maxRetries: 2,
  },
} as const;