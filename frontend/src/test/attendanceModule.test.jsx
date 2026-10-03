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

describe('Attendance Module Component', () => {
  const mockEmployees = [
    { id: 'emp-1', name: 'Alice Employee', email: 'alice@ems.com', role: 'EMPLOYEE', department: 'Engineering', designation: 'Developer', manager_id: 'mgr-1' },
    { id: 'mgr-1', name: 'Bob Manager', email: 'bob@ems.com', role: 'MANAGER', department: 'Management', designation: 'Lead', manager_id: 'hr-1' },
    { id: 'hr-1', name: 'Charlie HR', email: 'charlie@ems.com', role: 'HR', department: 'Human Resources', designation: 'HR Manager', manager_id: 'admin-1' },
    { id: 'admin-1', name: 'Diana Admin', email: 'diana@ems.com', role: 'ADMIN', department: 'Executive', designation: 'Admin', manager_id: null },
  ];

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: mockEmployees, total: 4 });
      }
      return Promise.resolve(null);
    });
  });

  it('EMPLOYEE can clock in and logoff early', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    expect(screen.getByTestId('tab-my-attendance')).toBeInTheDocument();
    expect(screen.getByTestId('clock-action-card')).toBeInTheDocument();
    expect(screen.getByTestId('attendance-calendar-card')).toBeInTheDocument();

    const clockInBtn = screen.getByTestId('clock-in-btn');
    expect(clockInBtn).toBeEnabled();

    // Clock In
    fireEvent.click(clockInBtn);
    expect(screen.getByTestId('toast-success')).toHaveTextContent(/clocked in successfully/i);

    // Early logoff test
    const earlyBtn = screen.getByTestId('early-logoff-btn');
    fireEvent.click(earlyBtn);
    expect(screen.getByTestId('toast-error')).toHaveTextContent(/EARLY LOGOFF/i);
    expect(screen.getAllByText(/EARLY LOGOFF/i).length).toBeGreaterThan(0);
  });

  it('MANAGER sees Team Attendance tab, Date Selector, Filter controls, and NOT MARKED YET status', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'mgr-1', role: ROLES.MANAGER }} />
      </BrowserRouter>
    );

    const teamTab = await screen.findByTestId('tab-team-attendance');
    expect(teamTab).toBeInTheDocument();

    fireEvent.click(teamTab);

    await waitFor(() => {
      expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
      expect(screen.getByTestId('hierarchy-attendance-card')).toBeInTheDocument();
      expect(screen.getByTestId('attendance-filter-bar')).toBeInTheDocument();
      expect(screen.getByTestId('date-picker')).toBeInTheDocument();
      // Extra filter dropdowns hidden for Manager's Team Attendance view
      expect(screen.queryByTestId('filter-department')).not.toBeInTheDocument();
      expect(screen.queryByTestId('filter-status')).not.toBeInTheDocument();

      expect(screen.getAllByText('Alice Employee').length).toBeGreaterThan(0);
      expect(screen.getAllByText('NOT MARKED YET').length).toBeGreaterThan(0);
    });
  });

  it('ADMIN can switch tabs and filter by Department and Status', async () => {
    render(
      <BrowserRouter>
        <Attendance user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    expect(screen.queryByTestId('clock-in-btn')).not.toBeInTheDocument();

    const empTab = screen.getByTestId('tab-admin-employees');
    const mgrTab = screen.getByTestId('tab-admin-managers');
    const hrTab = screen.getByTestId('tab-admin-hr');

    expect(empTab).toBeInTheDocument();
    expect(mgrTab).toBeInTheDocument();
    expect(hrTab).toBeInTheDocument();

    // Switch to Managers tab
    fireEvent.click(mgrTab);

    await waitFor(() => {
      expect(screen.getAllByText('Bob Manager').length).toBeGreaterThan(0);
    });

    // Test Department filter
    const deptSelect = screen.getByTestId('filter-department');
    fireEvent.change(deptSelect, { target: { value: 'Management' } });

    await waitFor(() => {
      expect(screen.getAllByText('Bob Manager').length).toBeGreaterThan(0);
    });
  });
});
