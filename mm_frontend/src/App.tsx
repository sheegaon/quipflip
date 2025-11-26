import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { useGame } from './contexts/GameContext';
import { AppProviders } from './contexts/AppProviders';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';
import NotificationDisplay from './components/NotificationDisplay';
import PingNotificationDisplay from './components/PingNotificationDisplay';
import { trackPageView } from './utils/googleAnalytics';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppErrorFallback } from './components/ErrorFallback';
import { OfflineBanner } from './components/OfflineBanner';
import GuestWelcomeOverlay from './components/GuestWelcomeOverlay';

// Suppress some logging messages
if (typeof window !== 'undefined') {
  const originalConsoleLog = console.log;
  console.log = (...args) => {
    const message = args.join(' ');
    // Vercel analytics warnings when blocked by ad blockers
    if (
      message.includes('[Vercel Web Analytics]') ||
      message.includes('[Vercel Speed Insights]') ||
      message.includes('va.vercel-scripts.com')
    ) {
      // Silently ignore Vercel analytics warnings
      return;
    }
    originalConsoleLog.apply(console, args);
  };
}

import { PageErrorFallback } from './components/ErrorFallback';

// Lazy load pages with error boundaries
const Landing = lazy(() => import('./pages/Landing'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const VoteRound = lazy(() => import('./pages/VoteRound'));
const CaptionRound = lazy(() => import('./pages/CaptionRound'));
const Results = lazy(() => import('./pages/Results'));
const GameHistory = lazy(() => import('./pages/GameHistory'));
const Quests = lazy(() => import('./pages/Quests'));
const Statistics = lazy(() => import('./pages/Statistics'));
const Leaderboard = lazy(() => import('./pages/Leaderboard'));
const OnlineUsers = lazy(() => import('./pages/OnlineUsers'));
const Settings = lazy(() => import('./pages/Settings'));
const Admin = lazy(() => import('./pages/Admin'));
const AdminFlagged = lazy(() => import('./pages/AdminFlagged'));
const BetaSurveyPage = lazy(() => import('./pages/BetaSurveyPage'));

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();

  if (!state.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

const suspenseFallback = (
  <div className="flex min-h-screen items-center justify-center bg-quip-navy/5">
    <span className="text-lg font-semibold text-quip-navy">Loading...</span>
  </div>
);

// Wrap page component with ErrorBoundary
const withPageErrorBoundary = (element: React.ReactNode) => (
  <ErrorBoundary fallback={PageErrorFallback}>
    {element}
  </ErrorBoundary>
);

const renderWithSuspense = (element: React.ReactNode) => (
  <Suspense fallback={suspenseFallback}>{withPageErrorBoundary(element)}</Suspense>
);

const renderProtectedRoute = (element: React.ReactNode) =>
  renderWithSuspense(<ProtectedRoute>{element}</ProtectedRoute>);

// App Routes
const AppRoutes: React.FC = () => {
  const { state } = useGame();
  const location = useLocation();

  useEffect(() => {
    trackPageView(`${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  // Show loading screen while initializing session
  const isInitializing = state.sessionState === 'checking';

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-quip-navy/5">
        <span className="text-lg font-semibold text-quip-navy">Loading...</span>
      </div>
    );
  }

  return (
    <>
      <OfflineBanner />
      <ErrorNotification />
      <NotificationDisplay />
      <PingNotificationDisplay />
      <GuestWelcomeOverlay />
      <TutorialOverlay />
      <Routes>
        <Route
          path="/"
          element={
            state.isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              renderWithSuspense(<Landing />)
            )
          }
        />
        <Route
          path="/dashboard"
          element={renderProtectedRoute(<Dashboard />)}
        />
        <Route
          path="/game/vote"
          element={renderProtectedRoute(<VoteRound />)}
        />
        <Route
          path="/game/caption"
          element={renderProtectedRoute(<CaptionRound />)}
        />
        <Route
          path="/game/results"
          element={renderProtectedRoute(<Results />)}
        />
        <Route
          path="/game/history"
          element={renderProtectedRoute(<GameHistory />)}
        />
        <Route
          path="/quests"
          element={renderProtectedRoute(<Quests />)}
        />
        <Route
          path="/statistics"
          element={renderProtectedRoute(<Statistics />)}
        />
        <Route
          path="/leaderboard"
          element={renderProtectedRoute(<Leaderboard />)}
        />
        <Route
          path="/online-users"
          element={renderProtectedRoute(<OnlineUsers />)}
        />
        <Route
          path="/settings"
          element={renderProtectedRoute(<Settings />)}
        />
        <Route
          path="/survey/beta"
          element={renderProtectedRoute(<BetaSurveyPage />)}
        />
        <Route
          path="/admin"
          element={renderProtectedRoute(<Admin />)}
        />
        <Route
          path="/admin/flags"
          element={renderProtectedRoute(<AdminFlagged />)}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
};

// Main App
function App() {
  return (
    <ErrorBoundary
      fallback={AppErrorFallback}
      isAppLevel={true}
      onError={(_error, _errorInfo, errorId) => {
        // Log to analytics if needed
        console.error('App-level error caught:', errorId);
      }}
    >
      <Router
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <AppProviders>
          <AppRoutes />
          <Analytics />
          <SpeedInsights />
        </AppProviders>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
