import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Attendance } from '../pages/Attendance.jsx';
import * as apiModule from '../lib/api.js';
import { ROLES } from '../lib/permissions.js';

vi.mock('../lib/api.js', async () => {
  const actual = await vi.importActual('../lib/api.js');
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      del: vi.fn(),
    },
  };
});

describe('Attendance Hierarchy Scope', () => {
  const mockEmployees = [
    { id: 'emp-1', name: 'Alice Employee', email: 'alice@ems.com', role: 'EMPLOYEE', manager_id: 'mgr-1' },
    { id: 'mgr-1', name: 'Bob Manager', email: 'bob@ems.com', role: 'MANAGER', manager_id: 'hr-1' },
    { id: 'hr-1', name: 'Charlie HR', email: 'charlie@ems.com', role: 'HR', manager_id: 'admin-1' },
    { id: 'admin-1', name: 'Diana Admin', email: 'diana@ems.com', role: 'ADMIN', manager_id: null },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: mockEmployees, total: 4 });
      }
      return Promise.resolve(null);
    });
  });

  it('EMPLOYEE sees My Attendance tab only', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    expect(screen.getByTestId('tab-my-attendance')).toBeInTheDocument();
    expect(screen.queryByTestId('tab-team-attendance')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tab-all-attendance')).not.toBeInTheDocument();
  });

  it('MANAGER sees Team Attendance tab', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'mgr-1', role: ROLES.MANAGER }} />
      </BrowserRouter>
    );

    expect(screen.getByTestId('tab-my-attendance')).toBeInTheDocument();
    expect(screen.getByTestId('tab-team-attendance')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tab-team-attendance'));

    await waitFor(() => {
      expect(screen.getAllByText('Alice Employee').length).toBeGreaterThan(0);
    });
  });

  it('HR sees Employee Attendance (All Staff) tab', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'hr-1', role: ROLES.HR }} />
      </BrowserRouter>
    );

    expect(screen.getByTestId('tab-my-attendance')).toBeInTheDocument();
    expect(screen.getByTestId('tab-all-attendance')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tab-all-attendance'));

    await waitFor(() => {
      expect(screen.getAllByText('Alice Employee').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Bob Manager').length).toBeGreaterThan(0);
    });
  });

  it('ADMIN sees role-specific tabs for Employees, Managers, and HR Staff', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    expect(screen.queryByTestId('tab-my-attendance')).not.toBeInTheDocument();
    expect(screen.getByTestId('tab-admin-employees')).toBeInTheDocument();
    expect(screen.getByTestId('tab-admin-managers')).toBeInTheDocument();
    expect(screen.getByTestId('tab-admin-hr')).toBeInTheDocument();
  });
});
