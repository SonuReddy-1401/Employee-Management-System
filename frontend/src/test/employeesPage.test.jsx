import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Employees } from '../pages/Employees.jsx';
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

describe('Employees Page Component', () => {
  const mockEmployees = [
    {
      id: 'emp-1',
      name: 'Alice Smith',
      email: 'alice@ems.com',
      department: 'Engineering',
      designation: 'Developer',
      manager_id: null,
      status: 'ACTIVE',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/employees?page=1&page_size=100')) {
        return Promise.resolve({ items: mockEmployees, total: 1 });
      }
      if (url.includes('/employees')) {
        return Promise.resolve({ items: mockEmployees, total: 1 });
      }
      return Promise.resolve(null);
    });
  });

  it('renders write buttons (+ Onboard Employee) for ADMIN and HR, but hides them for MANAGER', async () => {
    // 1. ADMIN
    const { unmount: unmountAdmin } = render(
      <BrowserRouter>
        <Employees user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId('onboard-employee-btn')).toBeInTheDocument();
    });
    unmountAdmin();

    // 2. HR
    const { unmount: unmountHR } = render(
      <BrowserRouter>
        <Employees user={{ id: 'hr-1', role: ROLES.HR }} />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId('onboard-employee-btn')).toBeInTheDocument();
    });
    unmountHR();

    // 3. MANAGER
    render(
      <BrowserRouter>
        <Employees user={{ id: 'mgr-1', role: ROLES.MANAGER }} />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('onboard-employee-btn')).not.toBeInTheDocument();
  });

  it('shows persistent ONBOARDING_FAILED panel on 502 saga failure', async () => {
    render(
      <BrowserRouter>
        <Employees user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('onboard-employee-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('onboard-employee-btn'));

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Bob Fail' } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'fail@ems.com' } });
    fireEvent.change(screen.getByLabelText(/^department \*/i), { target: { value: 'QA' } });
    fireEvent.change(screen.getByLabelText(/^designation \*/i), { target: { value: 'Tester' } });
    fireEvent.change(screen.getByLabelText(/initial password/i), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText(/monthly salary/i), { target: { value: '4000' } });

    // Mock 502 ONBOARDING_FAILED response
    apiModule.api.post.mockRejectedValueOnce(
      new apiModule.ApiError(502, 'ONBOARDING_FAILED', 'Saga execution failed')
    );

    fireEvent.click(screen.getByTestId('submit-onboard-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('onboarding-saga-error')).toHaveTextContent(
        'Onboarding steps were rolled back'
      );
    });
  });

  it('disables submit button while onboarding is pending and sends exactly ONE POST on rapid clicks', async () => {
    let resolvePost;
    const postPromise = new Promise((resolve) => {
      resolvePost = resolve;
    });
    apiModule.api.post.mockImplementationOnce(() => postPromise);

    render(
      <BrowserRouter>
        <Employees user={{ id: 'admin-1', role: ROLES.ADMIN }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('onboard-employee-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('onboard-employee-btn'));

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Single Post' } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'single@ems.com' } });
    fireEvent.change(screen.getByLabelText(/^department \*/i), { target: { value: 'Dev' } });
    fireEvent.change(screen.getByLabelText(/^designation \*/i), { target: { value: 'Dev' } });
    fireEvent.change(screen.getByLabelText(/initial password/i), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByLabelText(/monthly salary/i), { target: { value: '4000' } });

    const submitBtn = screen.getByTestId('submit-onboard-btn');
    fireEvent.click(submitBtn);
    fireEvent.click(submitBtn); // Second rapid click

    expect(submitBtn).toBeDisabled();
    expect(apiModule.api.post).toHaveBeenCalledTimes(1);

    resolvePost({ id: 'emp-new', status: 'ACTIVE' });
  });
});
