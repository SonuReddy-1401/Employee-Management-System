import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Login } from '../pages/Login.jsx';
import * as apiModule from '../lib/api.js';

vi.mock('../lib/api.js', async () => {
  const actual = await vi.importActual('../lib/api.js');
  return {
    ...actual,
    api: {
      post: vi.fn(),
    },
  };
});

describe('Login component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('renders login form with email and password inputs', () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('displays error toast on server login failure', async () => {
    apiModule.api.post.mockRejectedValueOnce(
      new apiModule.ApiError(401, 'UNAUTHORIZED', 'Invalid email or password')
    );

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'admin@ems.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toHaveTextContent('Invalid email or password');
    });
  });

  it('calls onLoginSuccess and redirects on successful login', async () => {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const body = btoa(JSON.stringify({ sub: 'admin-id', role: 'ADMIN', exp: Math.floor(Date.now() / 1000) + 3600 }))
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
    const mockToken = `${header}.${body}.sig`;

    apiModule.api.post.mockResolvedValueOnce({ access_token: mockToken });
    const onLoginSuccess = vi.fn();

    render(
      <BrowserRouter>
        <Login onLoginSuccess={onLoginSuccess} />
      </BrowserRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'admin@ems.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'AdminPassword123!' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(onLoginSuccess).toHaveBeenCalledWith(mockToken);
      expect(sessionStorage.getItem('access_token')).toBe(mockToken);
    });
  });
});
