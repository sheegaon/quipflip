import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { useGame } from './contexts/GameContext';
import { AppProviders } from './contexts/AppProviders';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';
import { trackPageView } from './utils/googleAnalytics';

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

const Landing = lazy(() => import('./pages/Landing'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const PromptRound = lazy(() => import('./pages/PromptRound'));
const CopyRound = lazy(() => import('./pages/CopyRound'));
const VoteRound = lazy(() => import('./pages/VoteRound'));
const Results = lazy(() => import('./pages/Results'));
const Tracking = lazy(() => import('./pages/Tracking'));
const Quests = lazy(() => import('./pages/Quests'));
const Statistics = lazy(() => import('./pages/Statistics'));
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

const renderWithSuspense = (element: React.ReactNode) => (
  <Suspense fallback={suspenseFallback}>{element}</Suspense>
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

  return (
    <>
      <ErrorNotification />
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
          path="/results"
          element={renderProtectedRoute(<Results />)}
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
  );
}

export default App;
