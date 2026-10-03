import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { getUser, clearSession, setupAutoLogout } from './lib/session.js';
import { canSee } from './lib/permissions.js';
import { Sidebar } from './components/Sidebar.jsx';
import { TopBar } from './components/TopBar.jsx';
import { Login } from './pages/Login.jsx';
import {
  Dashboard,
  Employees,
  Leave,
  Payroll,
  Notifications,
  System,
  NotAllowed,
} from './pages/PlaceholderPages.jsx';

export function ProtectedRoute({ children, path }) {
  const user = getUser();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const checkPath = path || location.pathname;
  if (!canSee(user.role, checkPath)) {
    return <Navigate to="/not-allowed" replace />;
  }

  return children;
}

export function AppLayout({ children, user, onLogout }) {
  return (
    <div className="app-layout">
      <Sidebar user={user} />
      <div className="main-content">
        <TopBar user={user} onLogout={onLogout} />
        <main className="page-container">{children}</main>
      </div>
    </div>
  );
}

export function AppContent() {
  const [user, setUser] = useState(() => getUser());

  const handleLogout = () => {
    clearSession();
    setUser(null);
  };

  const handleLoginSuccess = () => {
    const updatedUser = getUser();
    setUser(updatedUser);
    setupAutoLogout(handleLogout);
  };

  useEffect(() => {
    setupAutoLogout(handleLogout);
  }, []);

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" replace /> : <Login onLoginSuccess={handleLoginSuccess} />}
      />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute path="/dashboard">
            <AppLayout user={user} onLogout={handleLogout}>
              <Dashboard user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/employees"
        element={
          <ProtectedRoute path="/employees">
            <AppLayout user={user} onLogout={handleLogout}>
              <Employees user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/leave"
        element={
          <ProtectedRoute path="/leave">
            <AppLayout user={user} onLogout={handleLogout}>
              <Leave user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/payroll"
        element={
          <ProtectedRoute path="/payroll">
            <AppLayout user={user} onLogout={handleLogout}>
              <Payroll user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/notifications"
        element={
          <ProtectedRoute path="/notifications">
            <AppLayout user={user} onLogout={handleLogout}>
              <Notifications user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/system"
        element={
          <ProtectedRoute path="/system">
            <AppLayout user={user} onLogout={handleLogout}>
              <System user={user} />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/not-allowed"
        element={
          user ? (
            <AppLayout user={user} onLogout={handleLogout}>
              <NotAllowed />
            </AppLayout>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={user ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
