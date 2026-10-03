import React from 'react';
import { NavLink } from 'react-router-dom';
import { canSee } from '../lib/permissions.js';

const ALL_NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/employees', label: 'Employees' },
  { path: '/leave', label: 'Leave' },
  { path: '/payroll', label: 'Payroll' },
  { path: '/notifications', label: 'Notifications' },
  { path: '/system', label: 'System' },
];

export function Sidebar({ user }) {
  if (!user || !user.role) return null;

  const allowedItems = ALL_NAV_ITEMS.filter((item) => canSee(user.role, item.path));

  return (
    <aside className="sidebar" data-testid="sidebar">
      <div className="sidebar-header">EMS Portal</div>
      <nav className="sidebar-nav">
        {allowedItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
