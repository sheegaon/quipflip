/**
 * Thin wrapper around the browser Notification API used to surface party lobby
 * activity (a player joined / left) while the tab is in the background.
 *
 * Every call is a safe no-op when the API is unavailable or permission has not
 * been granted, so callers never need to feature-detect themselves.
 */

export type NotificationPermissionState = NotificationPermission | 'unsupported';

export interface ShowNotificationOptions {
  body?: string;
  /** Notifications sharing a tag collapse into one, avoiding stacks of toasts. */
  tag?: string;
  icon?: string;
  /**
   * Only show when the tab is actually backgrounded (default true). When the
   * user is already looking at the lobby the in-page activity feed is enough.
   */
  onlyWhenHidden?: boolean;
  /** Auto-close after this many ms (default 5000). */
  autoCloseMs?: number;
}

export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function getNotificationPermission(): NotificationPermissionState {
  if (!notificationsSupported()) return 'unsupported';
  return Notification.permission;
}

export async function requestNotificationPermission(): Promise<NotificationPermissionState> {
  if (!notificationsSupported()) return 'unsupported';
  if (Notification.permission !== 'default') return Notification.permission;
  try {
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

export function showBrowserNotification(title: string, options: ShowNotificationOptions = {}): void {
  if (!notificationsSupported() || Notification.permission !== 'granted') return;

  const { body, tag, icon, onlyWhenHidden = true, autoCloseMs = 5000 } = options;

  if (onlyWhenHidden && typeof document !== 'undefined' && !document.hidden) {
    return;
  }

  try {
    const notification = new Notification(title, { body, tag, icon });
    if (autoCloseMs > 0) {
      window.setTimeout(() => notification.close(), autoCloseMs);
    }
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
  } catch {
    // Some browsers throw if notifications are constructed without a service
    // worker (e.g. Android Chrome); fail silently — the in-app feed still works.
  }
}
