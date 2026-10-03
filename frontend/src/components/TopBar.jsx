import React from 'react';
import { Badge } from './Badge.jsx';

export function TopBar({ user, onLogout }) {
  if (!user) return null;

  return (
    <header className="top-bar" data-testid="top-bar">
      <div>
        <span style={{ marginRight: '0.5rem', color: 'var(--text-secondary)' }}>Role:</span>
        <Badge type={user.role}>{user.role}</Badge>
      </div>
      <button className="btn btn-danger" onClick={onLogout} data-testid="logout-btn">
        Logout
      </button>
    </header>
  );
}
