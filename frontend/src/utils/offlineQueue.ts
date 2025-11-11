export interface OfflineAction {
  id: string;
  type: 'api_call';
  method: string;
  url: string;
  data?: any;
  headers?: Record<string, string>;
  timestamp: number;
  retryCount: number;
  maxRetries: number;
}

const QUEUE_STORAGE_KEY = 'quipflip_offline_queue';
const MAX_QUEUE_SIZE = 100; // Prevent unlimited queue growth

/**
 * OfflineQueue Class
 *
 * Manages queuing of API calls when offline
 * Persists queue to localStorage for recovery after page refresh
 */
export class OfflineQueue {
  private queue: OfflineAction[] = [];
  private listeners: Array<(queue: OfflineAction[]) => void> = [];

  constructor() {
    this.loadQueue();
  }

  /**
   * Add an action to the queue
   */
  addAction(action: Omit<OfflineAction, 'id' | 'timestamp' | 'retryCount'>): string {
    // Check queue size limit
    if (this.queue.length >= MAX_QUEUE_SIZE) {
      console.warn('Offline queue is full. Removing oldest action.');
      this.queue.shift();
    }

    const newAction: OfflineAction = {
      ...action,
      id: this.generateId(),
      timestamp: Date.now(),
      retryCount: 0,
    };

    this.queue.push(newAction);
    this.persistQueue();
    this.notifyListeners();

    return newAction.id;
  }

  /**
   * Remove an action from the queue
   */
  removeAction(id: string): boolean {
    const initialLength = this.queue.length;
    this.queue = this.queue.filter(action => action.id !== id);

    if (this.queue.length !== initialLength) {
      this.persistQueue();
      this.notifyListeners();
      return true;
    }

    return false;
  }

  /**
   * Get all actions in the queue
   */
  getQueue(): OfflineAction[] {
    return [...this.queue];
  }

  /**
   * Get queue size
   */
  getQueueSize(): number {
    return this.queue.length;
  }

  /**
   * Clear the entire queue
   */
  clearQueue(): void {
    this.queue = [];
    this.persistQueue();
    this.notifyListeners();
  }

  /**
   * Increment retry count for an action
   */
  incrementRetryCount(id: string): boolean {
    const action = this.queue.find(a => a.id === id);
    if (action) {
      action.retryCount++;
      this.persistQueue();
      this.notifyListeners();
      return true;
    }
    return false;
  }

  /**
   * Check if an action has exceeded max retries
   */
  hasExceededMaxRetries(id: string): boolean {
    const action = this.queue.find(a => a.id === id);
    return action ? action.retryCount >= action.maxRetries : false;
  }

  /**
   * Subscribe to queue changes
   */
  subscribe(listener: (queue: OfflineAction[]) => void): () => void {
    this.listeners.push(listener);

    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  /**
   * Notify all listeners of queue changes
   */
  private notifyListeners(): void {
    this.listeners.forEach(listener => {
      try {
        listener([...this.queue]);
      } catch (error) {
        console.error('Error in offline queue listener:', error);
      }
    });
  }

  /**
   * Persist queue to localStorage
   */
  private persistQueue(): void {
    try {
      localStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(this.queue));
    } catch (error) {
      console.error('Failed to persist offline queue:', error);
    }
  }

  /**
   * Load queue from localStorage
   */
  private loadQueue(): void {
    try {
      const stored = localStorage.getItem(QUEUE_STORAGE_KEY);
      if (stored) {
        this.queue = JSON.parse(stored);
        console.log(`Loaded ${this.queue.length} actions from offline queue`);
      }
    } catch (error) {
      console.error('Failed to load offline queue:', error);
      this.queue = [];
    }
  }

  /**
   * Generate a unique ID for an action
   */
  private generateId(): string {
    return `action-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  }
}

// Singleton instance
export const offlineQueue = new OfflineQueue();

/**
 * Helper to check if an action should be queued when offline
 */
export const shouldQueueAction = (_method: string, url: string): boolean => {
  // Don't queue GET requests (they can just fail and retry)
  if (_method.toUpperCase() === 'GET') {
    return false;
  }

  // Don't queue auth requests
  if (url.includes('/auth/') || url.includes('/login') || url.includes('/logout')) {
    return false;
  }

  // Queue most POST, PUT, PATCH, DELETE requests
  return ['POST', 'PUT', 'PATCH', 'DELETE'].includes(_method.toUpperCase());
};

/**
 * Helper to determine if an action supports optimistic UI
 */
export const supportsOptimisticUI = (_method: string, url: string): boolean => {
  // Optimistic UI is good for mutations that are likely to succeed
  const optimisticEndpoints = [
    '/rounds/prompt',
    '/rounds/copy',
    '/rounds/vote',
    '/quests/claim',
  ];

  return optimisticEndpoints.some(endpoint => url.includes(endpoint));
};
