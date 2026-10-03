import { describe, it, expect } from 'vitest';
import { decodeToken, isExpired } from '../lib/jwt.js';

describe('jwt utility', () => {
  const createToken = (payload) => {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const body = btoa(JSON.stringify(payload))
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
    return `${header}.${body}.signature`;
  };

  it('decodes valid JWT token returning sub, role, and exp', () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const token = createToken({ sub: 'user-123', role: 'ADMIN', exp });
    const decoded = decodeToken(token);

    expect(decoded).toEqual({
      sub: 'user-123',
      role: 'ADMIN',
      exp,
    });
  });

  it('returns null for malformed or invalid JWT tokens', () => {
    expect(decodeToken(null)).toBeNull();
    expect(decodeToken('')).toBeNull();
    expect(decodeToken('invalid.token')).toBeNull();
    expect(decodeToken('a.b.c.d')).toBeNull();
    expect(decodeToken('a.not_json.c')).toBeNull();
  });

  it('correctly identifies expired and valid tokens', () => {
    const pastExp = Math.floor(Date.now() / 1000) - 100;
    const futureExp = Math.floor(Date.now() / 1000) + 3600;

    const expiredToken = createToken({ sub: 'user-1', role: 'HR', exp: pastExp });
    const validToken = createToken({ sub: 'user-2', role: 'HR', exp: futureExp });

    expect(isExpired(expiredToken)).toBe(true);
    expect(isExpired(validToken)).toBe(false);
    expect(isExpired('invalid-token')).toBe(true);
  });
});
