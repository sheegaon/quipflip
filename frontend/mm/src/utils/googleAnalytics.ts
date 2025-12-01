const getMeasurementId = (): string | undefined => {
  if (typeof window === 'undefined') {
    return import.meta.env.VITE_GA_MEASUREMENT_ID;
  }

  return window.GA_MEASUREMENT_ID ?? import.meta.env.VITE_GA_MEASUREMENT_ID;
};

const isGoogleAnalyticsReady = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  
  const measurementId = getMeasurementId();
  const gtag = window?.gtag;
  
  return Boolean(measurementId && typeof gtag === 'function');
};

export const trackPageView = (path: string): void => {
  if (typeof window === 'undefined') {
    return;
  }

  // If GA isn't ready yet, try again after a short delay
  if (!isGoogleAnalyticsReady()) {
    // Only retry once to avoid infinite loops
    setTimeout(() => {
      if (isGoogleAnalyticsReady()) {
        trackPageViewInternal(path);
      } else {
        // Only log in development mode to avoid console spam
        if (import.meta.env.DEV) {
          console.warn('Google Analytics not available for page tracking');
        }
      }
    }, 100);
    return;
  }

  trackPageViewInternal(path);
};

const trackPageViewInternal = (path: string): void => {
  const measurementId = getMeasurementId();
  const gtag = window?.gtag;

  if (!measurementId || typeof gtag !== 'function') {
    return;
  }

  gtag('config', measurementId, {
    page_path: path,
  });
};

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    GA_MEASUREMENT_ID?: string;
  }
}

export {};
