import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach } from 'vitest';
import { AppContent } from '../App.jsx';

describe('Route Guard & Navigation', () => {
  const createToken = (role) => {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const body = btoa(
      JSON.stringify({
        sub: `user-${role}`,
        role,
        exp: Math.floor(Date.now() / 1000) + 3600,
      })
    )
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
    return `${header}.${body}.sig`;
  };

  beforeEach(() => {
    sessionStorage.clear();
  });

  it('redirects unauthenticated users attempting to access protected route to /login', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AppContent />
      </MemoryRouter>
    );

    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('redirects users with forbidden role to Not allowed page', () => {
    sessionStorage.setItem('access_token', createToken('EMPLOYEE'));

    render(
      <MemoryRouter initialEntries={['/system']}>
        <AppContent />
      </MemoryRouter>
    );

    expect(screen.getByText(/not allowed/i)).toBeInTheDocument();
  });

  it('allows access to permitted route for authorized role', () => {
    sessionStorage.setItem('access_token', createToken('ADMIN'));

    render(
      <MemoryRouter initialEntries={['/system']}>
        <AppContent />
      </MemoryRouter>
    );

    expect(screen.getByText(/system status & logs/i)).toBeInTheDocument();
  });
});
