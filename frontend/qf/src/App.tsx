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
import { ErrorBoundary } from '@crowdcraft/components/ErrorBoundary.tsx';
import { AppErrorFallback } from '@crowdcraft/components/ErrorFallback.tsx';
import { OfflineBanner } from './components/OfflineBanner';
import NewUserWelcomeOverlay from './components/NewUserWelcomeOverlay';

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

import { PageErrorFallback } from '@crowdcraft/components/ErrorFallback.tsx';

// Lazy load pages with error boundaries
const Landing = lazy(() => import('./pages/Landing'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const PromptRound = lazy(() => import('./pages/PromptRound'));
const CopyRound = lazy(() => import('./pages/CopyRound'));
const VoteRound = lazy(() => import('./pages/VoteRound'));
const PracticePrompt = lazy(() => import('./pages/PracticePrompt'));
const PracticeCopy = lazy(() => import('./pages/PracticeCopy'));
const PracticeCopy2 = lazy(() => import('./pages/PracticeCopy2'));
const PracticeVote = lazy(() => import('./pages/PracticeVote'));
const Results = lazy(() => import('./pages/Results'));
const Completed = lazy(() => import('./pages/Completed'));
const PhrasesetReview = lazy(() => import('./pages/PhrasesetReview'));
const Tracking = lazy(() => import('./pages/Tracking'));
const Quests = lazy(() => import('./pages/Quests'));
const Statistics = lazy(() => import('./pages/Statistics'));
const Leaderboard = lazy(() => import('./pages/Leaderboard'));
const OnlineUsers = lazy(() => import('./pages/OnlineUsers'));
const Settings = lazy(() => import('./pages/Settings'));
const Admin = lazy(() => import('./pages/Admin'));
const AdminFlagged = lazy(() => import('./pages/AdminFlagged'));
const BetaSurveyPage = lazy(() => import('./pages/BetaSurveyPage'));
const PartyMode = lazy(() => import('./pages/PartyMode'));
const PartyLobby = lazy(() => import('./pages/PartyLobby'));
const PartyGame = lazy(() => import('./pages/PartyGame'));
const PartyResults = lazy(() => import('./pages/PartyResults'));

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();

  if (!state.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

const suspenseFallback = (
  <div className="flex min-h-screen items-center justify-center bg-ccl-navy/5">
    <span className="text-lg font-semibold text-ccl-navy">Loading...</span>
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
      <div className="flex min-h-screen items-center justify-center bg-ccl-navy/5">
        <span className="text-lg font-semibold text-ccl-navy">Loading...</span>
      </div>
    );
  }

  return (
    <>
      <OfflineBanner />
      <ErrorNotification />
      <NotificationDisplay />
      <PingNotificationDisplay />
      <NewUserWelcomeOverlay />
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
          path="/prompt"
          element={renderProtectedRoute(<PromptRound />)}
        />
        <Route
          path="/copy"
          element={renderProtectedRoute(<CopyRound />)}
        />
        <Route
          path="/vote"
          element={renderProtectedRoute(<VoteRound />)}
        />
        <Route
          path="/practice/prompt"
          element={renderProtectedRoute(<PracticePrompt />)}
        />
        <Route
          path="/practice/copy"
          element={renderProtectedRoute(<PracticeCopy />)}
        />
        <Route
          path="/practice/copy2"
          element={renderProtectedRoute(<PracticeCopy2 />)}
        />
        <Route
          path="/practice/vote"
          element={renderProtectedRoute(<PracticeVote />)}
        />
        <Route
          path="/results"
          element={renderProtectedRoute(<Results />)}
        />
        <Route
          path="/completed"
          element={renderProtectedRoute(<Completed />)}
        />
        <Route
          path="/phraseset/:phrasesetId/review"
          element={renderProtectedRoute(<PhrasesetReview />)}
        />
        <Route
          path="/tracking"
          element={renderProtectedRoute(<Tracking />)}
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
          path="/party"
          element={renderProtectedRoute(<PartyMode />)}
        />
        <Route
          path="/party/:sessionId"
          element={renderProtectedRoute(<PartyLobby />)}
        />
        <Route
          path="/party/game/:sessionId"
          element={renderProtectedRoute(<PartyGame />)}
        />
        <Route
          path="/party/results/:sessionId"
          element={renderProtectedRoute(<PartyResults />)}
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
