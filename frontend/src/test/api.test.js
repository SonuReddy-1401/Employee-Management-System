import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiError } from '../lib/api.js';
import * as session from '../lib/session.js';

describe('api fetch wrapper', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('handles successful 200 response with JSON parsing', async () => {
    const mockData = { id: 1, name: 'Alice' };
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(mockData),
    });

    const res = await api.get('/employees');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/api/employees', expect.objectContaining({ method: 'GET' }));
    expect(res).toEqual(mockData);
  });

  it('handles 204 No Content response returning null', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const res = await api.del('/employees/123');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(res).toBeNull();
  });

  it('maps project error JSON on non-2xx responses into ApiError', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({
        error: { code: 'DUPLICATE_EMAIL', message: 'Email already exists' },
      }),
    });

    try {
      await api.post('/employees', { email: 'dup@test.com' });
      expect.fail('Should have thrown ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(409);
      expect(err.code).toBe('DUPLICATE_EMAIL');
      expect(err.message).toBe('Email already exists');
    }
  });

  it('clears session on 401 for non-login endpoints and does not retry', async () => {
    sessionStorage.setItem('access_token', 'expired.mock.token');
    const clearSessionSpy = vi.spyOn(session, 'clearSession');

    fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({
        error: { code: 'UNAUTHORIZED', message: 'Token expired' },
      }),
    });

    try {
      await api.get('/employees');
    } catch (err) {
      expect(err.status).toBe(401);
    }

    expect(fetch).toHaveBeenCalledTimes(1); // No retries
    expect(clearSessionSpy).toHaveBeenCalled();
  });
});
