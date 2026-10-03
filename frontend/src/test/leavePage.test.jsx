import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Leave } from '../pages/Leave.jsx';
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

describe('Leave Page Component', () => {
  const mockEmployees = [
    { id: 'emp-1', name: 'Alice', email: 'alice@ems.com', status: 'ACTIVE' },
    { id: 'emp-2', name: 'Bob', email: 'bob@ems.com', status: 'ACTIVE' },
  ];

  const mockLeaves = [
    {
      id: 'leave-1',
      employee_id: 'emp-1',
      manager_id: 'mgr-1',
      start_date: '2026-03-02',
      end_date: '2026-03-06',
      leave_type: 'PAID',
      days: 5,
      reason: 'Vacation',
      status: 'PENDING',
      decided_by: null,
      created_at: '2026-03-01T10:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: mockEmployees, total: 2 });
      }
      if (url.includes('/leaves/balance/')) {
        return Promise.resolve({ employee_id: 'emp-1', year: 2026, allowance: 20, used: 5, remaining: 15 });
      }
      if (url.includes('/leaves')) {
        return Promise.resolve({ items: mockLeaves, total: 1 });
      }
      return Promise.resolve(null);
    });
  });

  it('ADMIN sees employee balance selector and has no default subject', async () => {
    render(
      <BrowserRouter>
        <Leave user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('balance-employee-select')).toBeInTheDocument();
    });

    expect(screen.getByTestId('balance-employee-select')).toHaveValue('');
    expect(screen.getByText(/please select an employee to view leave balance/i)).toBeInTheDocument();
  });

  it('renders EMPLOYEE leave balance (allowance, used, remaining) with URL containing user id and year', async () => {
    const currentYear = new Date().getUTCFullYear();
    render(
      <BrowserRouter>
        <Leave user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/allowance:/i)).toHaveTextContent('Allowance: 20 days');
      expect(screen.getByText(/used:/i)).toHaveTextContent('Used: 5 days');
      expect(screen.getByText(/remaining:/i)).toHaveTextContent('Remaining: 15 days');
    });

    expect(apiModule.api.get).toHaveBeenCalledWith(`/leaves/balance/emp-1?year=${currentYear}`);
  });

  it('renders MANAGER leave balance (allowance, used, remaining) with URL containing user id and year', async () => {
    const currentYear = new Date().getUTCFullYear();
    render(
      <BrowserRouter>
        <Leave user={{ id: 'mgr-456', role: ROLES.MANAGER }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/allowance:/i)).toHaveTextContent('Allowance: 20 days');
      expect(screen.getByText(/used:/i)).toHaveTextContent('Used: 5 days');
      expect(screen.getByText(/remaining:/i)).toHaveTextContent('Remaining: 15 days');
    });

    expect(apiModule.api.get).toHaveBeenCalledWith(`/leaves/balance/mgr-456?year=${currentYear}`);
  });

  it('displays error message in balance card when balance API fails', async () => {
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: mockEmployees, total: 2 });
      }
      if (url.includes('/leaves/balance/')) {
        return Promise.reject(new Error('Failed to load leave balance details'));
      }
      if (url.includes('/leaves')) {
        return Promise.resolve({ items: mockLeaves, total: 1 });
      }
      return Promise.resolve(null);
    });

    render(
      <BrowserRouter>
        <Leave user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('balance-error-msg')).toHaveTextContent('Failed to load leave balance details');
    });
  });

  it('EMPLOYEE role cannot see Approve button on leaves table', async () => {
    render(
      <BrowserRouter>
        <Leave user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('approve-btn-leave-1')).not.toBeInTheDocument();
  });

  it('blocks weekend-only date range submit without calling the API', async () => {
    render(
      <BrowserRouter>
        <Leave user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    // 2026-03-07 (Sat) to 2026-03-08 (Sun)
    fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: '2026-03-07' } });
    fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-03-08' } });

    const submitBtn = screen.getByTestId('submit-leave-request-btn');

    expect(screen.getByText(/leave range contains no weekdays/i)).toBeInTheDocument();
    expect(submitBtn).toBeDisabled();

    fireEvent.click(submitBtn);
    expect(apiModule.api.post).not.toHaveBeenCalled();
  });

  it('displays toast error message on 409 overlap error response from API', async () => {
    render(
      <BrowserRouter>
        <Leave user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: '2026-03-02' } });
    fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-03-06' } });

    apiModule.api.post.mockRejectedValueOnce(
      new apiModule.ApiError(409, 'OVERLAPPING_LEAVE', 'Requested leave dates overlap with existing leave')
    );

    const submitBtn = screen.getByTestId('submit-leave-request-btn');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toHaveTextContent(
        'Requested leave dates overlap with existing leave'
      );
    });
  });
});
