import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Payroll } from '../pages/Payroll.jsx';
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

describe('Payroll Page Component', () => {
  const mockPayslips = [
    {
      id: 'p-1',
      employee_id: 'emp-1',
      month: '2026-02',
      gross_salary: '5000.00',
      unpaid_leave_days: 1,
      deductions: '250.00',
      net_salary: '4750.00',
      created_at: '2026-03-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: [{ id: 'emp-1', name: 'Alice' }] });
      }
      if (url.includes('/payslips/')) {
        return Promise.resolve(mockPayslips);
      }
      return Promise.resolve(null);
    });
  });

  it('renders Run Payroll card for ADMIN and HR, but hides it for EMPLOYEE', async () => {
    // 1. ADMIN
    const { unmount: unmountAdmin } = render(
      <BrowserRouter>
        <Payroll user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId('run-payroll-btn')).toBeInTheDocument();
    });
    unmountAdmin();

    // 2. EMPLOYEE
    render(
      <BrowserRouter>
        <Payroll user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('2026-02')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('run-payroll-btn')).not.toBeInTheDocument();
    expect(screen.queryByTestId('payroll-employee-select')).not.toBeInTheDocument();
  });

  it('blocks malformed month without calling API', async () => {
    render(
      <BrowserRouter>
        <Payroll user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('run-payroll-btn')).toBeInTheDocument();
    });

    const monthInput = screen.getByLabelText(/target month/i);
    fireEvent.change(monthInput, { target: { value: 'invalid-month' } });

    fireEvent.click(screen.getByTestId('run-payroll-btn'));

    expect(screen.getByText(/month must be in YYYY-MM format/i)).toBeInTheDocument();
    expect(apiModule.api.post).not.toHaveBeenCalled();
  });

  it('requires confirm dialog before POST, shows created/skipped result, and locks submit on rapid click', async () => {
    let resolvePost;
    const postPromise = new Promise((resolve) => {
      resolvePost = resolve;
    });
    apiModule.api.post.mockImplementationOnce(() => postPromise);

    render(
      <BrowserRouter>
        <Payroll user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('run-payroll-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('run-payroll-btn'));

    // Confirm dialog opens
    expect(screen.getByText(/confirm payroll run/i)).toBeInTheDocument();

    const confirmBtn = screen.getByTestId('confirm-dialog-btn');
    fireEvent.click(confirmBtn);
    fireEvent.click(confirmBtn); // Rapid second click

    expect(apiModule.api.post).toHaveBeenCalledTimes(1);

    resolvePost({ created: 10, skipped: 2 });

    await waitFor(() => {
      expect(screen.getByTestId('payroll-run-result')).toHaveTextContent(
        'Created 10 payslips, Skipped 2 existing profiles'
      );
    });
  });

  it('displays 422 error message on failure', async () => {
    render(
      <BrowserRouter>
        <Payroll user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('run-payroll-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('run-payroll-btn'));
    expect(screen.getByText(/confirm payroll run/i)).toBeInTheDocument();

    apiModule.api.post.mockRejectedValueOnce(
      new apiModule.ApiError(422, 'UNPROCESSABLE_ENTITY', 'Payroll profile missing for active employee')
    );

    fireEvent.click(screen.getByTestId('confirm-dialog-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toHaveTextContent(
        'Payroll profile missing for active employee'
      );
    });
  });
});
