import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Notifications } from '../pages/Notifications.jsx';
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

describe('Notifications Page Component', () => {
  const mockNotifications = [
    {
      id: 'n-1',
      employee_id: 'emp-1',
      event_type: 'LeaveApproved',
      message: 'Your leave request for 2026-03-02 was approved.',
      created_at: '2026-03-01T12:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.get.mockImplementation((url) => {
      if (url.includes('/notifications/')) {
        return Promise.resolve(mockNotifications);
      }
      return Promise.resolve([]);
    });
  });

  it('sends limit parameter in API request and refetches on Refresh click', async () => {
    render(
      <BrowserRouter>
        <Notifications user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/your leave request for 2026-03-02 was approved/i)).toBeInTheDocument();
    });

    expect(apiModule.api.get).toHaveBeenCalledWith('/notifications/emp-1?limit=50');

    // Change limit selector
    const limitSelect = screen.getByTestId('notif-limit-select');
    fireEvent.change(limitSelect, { target: { value: '100' } });

    await waitFor(() => {
      expect(apiModule.api.get).toHaveBeenCalledWith('/notifications/emp-1?limit=100');
    });

    // Refresh click
    fireEvent.click(screen.getByTestId('refresh-notifications-btn'));
    expect(apiModule.api.get).toHaveBeenCalledTimes(3);
  });

  it('handles empty notifications list gracefully with EmptyState', async () => {
    apiModule.api.get.mockResolvedValueOnce([]);

    render(
      <BrowserRouter>
        <Notifications user={{ id: 'emp-1', role: ROLES.EMPLOYEE }} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toHaveTextContent('No notifications found for this user.');
    });
  });
});
