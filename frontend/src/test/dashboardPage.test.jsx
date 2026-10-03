import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Dashboard } from '../pages/Dashboard.jsx';
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

describe('Dashboard Page Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page_size=100')) {
        return Promise.resolve({ items: [{ id: 'emp-1', name: 'Alice' }] });
      }
      if (url.includes('/employees?page_size=1')) {
        return Promise.resolve({ total: 42 });
      }
      if (url.includes('/leaves/balance/')) {
        return Promise.resolve({ employee_id: 'emp-1', year: 2026, allowance: 20, used: 5, remaining: 15 });
      }
      if (url.includes('/leaves?status=PENDING&page_size=1')) {
        return Promise.resolve({ total: 7 });
      }
      if (url.includes('/leaves?status=PENDING&page_size=100')) {
        return Promise.resolve({ items: [] });
      }
      if (url.includes('/leaves?page=1&page_size=5')) {
        return Promise.resolve({ items: [] });
      }
      if (url.includes('/notifications/')) {
        return Promise.resolve([
          { id: 'n-1', event_type: 'LeaveApproved', message: 'Approved!', created_at: '2026-03-01T00:00:00Z' },
        ]);
      }
      return Promise.resolve(null);
    });
  });

  it('renders ADMIN cards with NO personal cards and total API request count <= 6', async () => {
    render(
      <BrowserRouter>
        <Dashboard user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('headcount-card')).toBeInTheDocument();
      expect(screen.getByTestId('total-pending-leaves-card')).toBeInTheDocument();
      expect(screen.getByTestId('recent-leaves-card')).toBeInTheDocument();
    });

    // ADMIN must NOT have personal cards
    expect(screen.queryByTestId('leave-balance-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dashboard-notifications-card')).not.toBeInTheDocument();

    // Verify request budget <= 6
    expect(apiModule.api.get.mock.calls.length).toBeLessThanOrEqual(6);
  });

  it('renders HR cards with total API request count <= 6', async () => {
    render(
      <BrowserRouter>
        <Dashboard user={{ id: 'hr-1', role: ROLES.HR }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('headcount-card')).toBeInTheDocument();
      expect(screen.getByTestId('total-pending-leaves-card')).toBeInTheDocument();
      expect(screen.getByTestId('recent-leaves-card')).toBeInTheDocument();
    });

    expect(apiModule.api.get.mock.calls.length).toBeLessThanOrEqual(6);
  });

  it('renders MANAGER cards including "Awaiting my decision" section and balance numbers with request count <= 6', async () => {
    const currentYear = new Date().getUTCFullYear();
    render(
      <BrowserRouter>
        <Dashboard user={{ id: 'mgr-1', role: ROLES.MANAGER }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('leave-balance-card')).toBeInTheDocument();
      expect(screen.getByTestId('leave-balance-card')).toHaveTextContent('15 days remaining');
      expect(screen.getByTestId('leave-balance-card')).toHaveTextContent('Used: 5 / Allowance: 20');
      expect(screen.getByTestId('my-pending-leaves-card')).toBeInTheDocument();
      expect(screen.getByTestId('manager-decision-card')).toBeInTheDocument();
      expect(screen.getByTestId('dashboard-notifications-card')).toBeInTheDocument();
    });

    // Verify URL contains user id and year
    expect(apiModule.api.get).toHaveBeenCalledWith(`/leaves/balance/mgr-1?year=${currentYear}`);
    expect(apiModule.api.get.mock.calls.length).toBeLessThanOrEqual(6);
  });

  it('renders EMPLOYEE balance (allowance, used, remaining) with URL containing signed-in user id and year', async () => {
    const currentYear = new Date().getUTCFullYear();
    render(
      <BrowserRouter>
        <Dashboard user={{ id: 'emp-123', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('leave-balance-card')).toBeInTheDocument();
      expect(screen.getByTestId('leave-balance-card')).toHaveTextContent('15 days remaining');
      expect(screen.getByTestId('leave-balance-card')).toHaveTextContent('Used: 5 / Allowance: 20');
    });

    expect(apiModule.api.get).toHaveBeenCalledWith(`/leaves/balance/emp-123?year=${currentYear}`);
    expect(screen.queryByTestId('manager-decision-card')).not.toBeInTheDocument();
    expect(apiModule.api.get.mock.calls.length).toBeLessThanOrEqual(6);
  });

  it('isolates card failures so one failed endpoint shows error message in card instead of blank numbers', async () => {
    // Fail balance endpoint specifically
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/leaves/balance/')) {
        return Promise.reject(new Error('Network error on balance'));
      }
      if (url.includes('/leaves?status=PENDING&page_size=1')) {
        return Promise.resolve({ total: 3 });
      }
      if (url.includes('/notifications/')) {
        return Promise.resolve([
          { id: 'n-1', event_type: 'LeaveApproved', message: 'Approved!', created_at: '2026-03-01T00:00:00Z' },
        ]);
      }
      return Promise.resolve(null);
    });

    render(
      <BrowserRouter>
        <Dashboard user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('my-pending-leaves-card')).toHaveTextContent('3');
      expect(screen.getByTestId('dashboard-notifications-card')).toHaveTextContent('Approved!');
    });

    // Balance card displays explicit error message instead of blank numbers
    expect(screen.getByTestId('leave-balance-card')).toHaveTextContent('Network error on balance');
  });
});
