import React from 'react';

function PageLayout({ title, user }) {
  return (
    <div className="card">
      <h1 className="card-title">{title}</h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Welcome! Signed-in role: <strong>{user?.role || 'Unknown'}</strong> (ID: {user?.id || 'N/A'})
      </p>
    </div>
  );
}

export function Dashboard({ user }) {
  return <PageLayout title="Dashboard" user={user} />;
}

export function Employees({ user }) {
  return <PageLayout title="Employees" user={user} />;
}

export function Leave({ user }) {
  return <PageLayout title="Leave Management" user={user} />;
}

export function Payroll({ user }) {
  return <PageLayout title="Payroll & Payslips" user={user} />;
}

export function Notifications({ user }) {
  return <PageLayout title="Notifications" user={user} />;
}

export function System({ user }) {
  return <PageLayout title="System Status & Logs" user={user} />;
}

export function NotAllowed() {
  return (
    <div className="card">
      <h1 className="card-title" style={{ color: 'var(--accent-danger)' }}>
        Not Allowed
      </h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        You do not have permission to access this page.
      </p>
    </div>
  );
}
