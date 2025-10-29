import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { useGame } from './contexts/GameContext';
import { AppProviders } from './contexts/AppProviders';
import { Landing } from './pages/Landing';
import { Dashboard } from './pages/Dashboard';
import { PromptRound } from './pages/PromptRound';
import { CopyRound } from './pages/CopyRound';
import { VoteRound } from './pages/VoteRound';
import { Results } from './pages/Results';
import { Tracking } from './pages/Tracking';
import { Quests } from './pages/Quests';
import Statistics from './pages/Statistics';
import Settings from './pages/Settings';
import Admin from './pages/Admin';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';
import { trackPageView } from './utils/googleAnalytics';

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();

  if (!state.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

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
        <Route path="/" element={state.isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/prompt"
          element={
            <ProtectedRoute>
              <PromptRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/copy"
          element={
            <ProtectedRoute>
              <CopyRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vote"
          element={
            <ProtectedRoute>
              <VoteRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/results"
          element={
            <ProtectedRoute>
              <Results />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tracking"
          element={
            <ProtectedRoute>
              <Tracking />
            </ProtectedRoute>
          }
        />
        <Route
          path="/quests"
          element={
            <ProtectedRoute>
              <Quests />
            </ProtectedRoute>
          }
        />
        <Route
          path="/statistics"
          element={
            <ProtectedRoute>
              <Statistics />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <Admin />
            </ProtectedRoute>
          }
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
