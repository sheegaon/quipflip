const getMeasurementId = (): string | undefined => {
  if (typeof window === 'undefined') {
    return import.meta.env.VITE_GA_MEASUREMENT_ID;
  }

  return window.GA_MEASUREMENT_ID || import.meta.env.VITE_GA_MEASUREMENT_ID;
};

export const trackPageView = (path: string): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const measurementId = getMeasurementId();
  const gtag = window.gtag;

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
