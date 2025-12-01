import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AppProviders } from './contexts/AppProviders';
import { useIRGame } from './contexts/IRGameContext';
import NotificationDisplay from './components/NotificationDisplay';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import BackronymCreate from './pages/BackronymCreate';
import SetTracking from './pages/SetTracking';
import Voting from './pages/Voting';
import Results from './pages/Results';
import Settings from './pages/Settings';
import './App.css';

if (typeof window !== 'undefined') {
  const originalConsoleLog = console.log;
  console.log = (...args) => {
    const message = args.join(' ');
    if (
      message.includes('[Vercel Web Analytics]') ||
      message.includes('[Vercel Speed Insights]') ||
      message.includes('va.vercel-scripts.com')
    ) {
      return;
    }
    originalConsoleLog.apply(console, args);
  };
}

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useIRGame();
  return isAuthenticated ? <>{children}</> : <Navigate to="/" replace />;
};

const AppRoutes: React.FC = () => {
  const { sessionState } = useIRGame();

  // Show loading screen while initializing session
  const isInitializing = sessionState === 'checking';

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <span className="text-lg font-semibold text-gray-900">Loading...</span>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<Landing />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/create"
        element={
          <ProtectedRoute>
            <BackronymCreate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tracking/:setId"
        element={
          <ProtectedRoute>
            <SetTracking />
          </ProtectedRoute>
        }
      />
      <Route
        path="/voting/:setId"
        element={
          <ProtectedRoute>
            <Voting />
          </ProtectedRoute>
        }
      />
      <Route
        path="/results/:setId"
        element={
          <ProtectedRoute>
            <Results />
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

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppProviders>
        <AppRoutes />
        <NotificationDisplay />
        <ErrorNotification />
        <TutorialOverlay />
        <Analytics />
        <SpeedInsights />
      </AppProviders>
    </Router>
  );
};

export default App;
