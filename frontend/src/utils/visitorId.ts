/**
 * Visitor ID Utility
 * Manages anonymous visitor tracking using both localStorage and cookies
 * for maximum persistence across sessions and domains
 */

const VISITOR_ID_KEY = 'quipflip_vid';
const COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year in seconds

/**
 * Generate a UUID v4
 * Uses crypto.randomUUID() for cryptographic security in modern browsers
 * Falls back to Math.random() implementation for legacy support
 */
function generateUUID(): string {
  // Use the standard crypto.randomUUID() if available (modern browsers, HTTPS)
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  // Fallback for older browsers or non-secure contexts
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Set a first-party cookie
 */
function setCookie(name: string, value: string, maxAge: number): void {
  document.cookie = `${name}=${value}; max-age=${maxAge}; path=/; SameSite=Lax`;
}

/**
 * Get a cookie value by name
 */
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? match[2] : null;
}

/**
 * Get or create visitor ID
 * Checks both localStorage and cookie for persistence
 * Returns the visitor ID (existing or newly created)
 */
export function getOrCreateVisitorId(): string {
  // First, check localStorage
  let visitorId = localStorage.getItem(VISITOR_ID_KEY);

  // If not in localStorage, check cookie
  if (!visitorId) {
    visitorId = getCookie(VISITOR_ID_KEY);
    if (visitorId) {
      // Sync from cookie to localStorage
      localStorage.setItem(VISITOR_ID_KEY, visitorId);
    }
  }

  // If still no visitor ID, create a new one
  if (!visitorId) {
    visitorId = generateUUID();
    localStorage.setItem(VISITOR_ID_KEY, visitorId);
    setCookie(VISITOR_ID_KEY, visitorId, COOKIE_MAX_AGE);
  } else {
    // Ensure cookie is set (refresh max-age)
    setCookie(VISITOR_ID_KEY, visitorId, COOKIE_MAX_AGE);
  }

  return visitorId;
}

/**
 * Get existing visitor ID without creating a new one
 * Returns null if no visitor ID exists
 */
export function getVisitorId(): string | null {
  return localStorage.getItem(VISITOR_ID_KEY) || getCookie(VISITOR_ID_KEY);
}

/**
 * Check if this is a returning visitor
 */
export function isReturningVisitor(): boolean {
  return getVisitorId() !== null;
}

/**
 * Clear visitor ID (useful for testing or privacy)
 */
export function clearVisitorId(): void {
  localStorage.removeItem(VISITOR_ID_KEY);
  // Set cookie with expired date to delete it
  document.cookie = `${VISITOR_ID_KEY}=; max-age=0; path=/`;
}
