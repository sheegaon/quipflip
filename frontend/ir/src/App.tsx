import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AppProviders } from './contexts/AppProviders';
import { useIRGame } from './contexts/IRGameContext';
import NotificationDisplay from './components/NotificationDisplay';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';
import Landing from './pages/Landing';
import MagicLink from './pages/MagicLink';
import Dashboard from './pages/Dashboard';
import BackronymCreate from './pages/BackronymCreate';
import SetTracking from './pages/SetTracking';
import Voting from './pages/Voting';
import Results from './pages/Results';
import Account from './pages/Account';
import Settings from './pages/Settings';
import './App.css';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useIRGame();
  return isAuthenticated ? <>{children}</> : <Navigate to="/" replace />;
};

const AppRoutes: React.FC = () => {
  const { sessionState, isAuthenticated } = useIRGame();

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
      <Route
        path="/"
        element={
          isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <Landing />
          )
        }
      />
      <Route path="/auth/magic-link" element={<MagicLink />} />

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
        path="/account"
        element={
          <ProtectedRoute>
            <Account />
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
      </AppProviders>
    </Router>
  );
};

export default App;
