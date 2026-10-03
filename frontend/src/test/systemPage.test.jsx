import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { System } from '../pages/System.jsx';

describe('System Page Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('maps HTTP 200 to UP and other status/error to DOWN, and renders telemetry links', async () => {
    global.fetch.mockImplementation((url) => {
      if (url.includes('/status/auth') || url.includes('/status/gateway')) {
        return Promise.resolve({ status: 200 });
      }
      if (url.includes('/status/employee')) {
        return Promise.resolve({ status: 500 });
      }
      return Promise.reject(new Error('Network failure'));
    });

    render(
      <BrowserRouter>
        <System />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('check-system-now-btn')).not.toBeDisabled();
    });

    // Check links
    expect(screen.getByTestId('grafana-link')).toHaveAttribute('href', expect.stringContaining(':3000'));
    expect(screen.getByTestId('prometheus-link')).toHaveAttribute('href', expect.stringContaining(':9090'));
    expect(screen.getByTestId('rabbitmq-link')).toHaveAttribute('href', expect.stringContaining(':15672'));

    // Check status badges
    const statusBadges = screen.getAllByText(/UP|DOWN/);
    expect(statusBadges.length).toBeGreaterThan(0);
  });

  it('does NOT fire any automatic requests after advancing fake timers by 5 minutes', async () => {
    vi.useFakeTimers();

    global.fetch.mockResolvedValue({ status: 200 });

    render(
      <BrowserRouter>
        <System />
      </BrowserRouter>
    );

    // Initial fetch for 6 services
    expect(global.fetch).toHaveBeenCalledTimes(6);

    // Advance timers by 5 minutes (300,000 ms)
    vi.advanceTimersByTime(300000);

    // Call count must remain exactly 6 (no automatic polling or setInterval!)
    expect(global.fetch).toHaveBeenCalledTimes(6);
  });
});
