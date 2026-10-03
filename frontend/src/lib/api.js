import { getToken, clearSession } from './session.js';

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'UNKNOWN_ERROR';
    this.message = message || `HTTP ${status}`;
  }
}

export async function request(path, options = {}) {
  const url = path.startsWith('/') ? `/api${path}` : `/api/${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (fetchErr) {
    throw new ApiError(0, 'NETWORK_ERROR', fetchErr.message || 'Network request failed');
  }

  if (response.status === 401 && !path.includes('/auth/login')) {
    clearSession();
    if (typeof window !== 'undefined' && window.location) {
      try {
        window.location.href = '/login';
      } catch (e) {
        // Ignored in test environment
      }
    }
  }

  if (!response.ok) {
    let errorData = null;
    try {
      errorData = await response.json();
    } catch (e) {
      // Body was not JSON
    }

    const code = errorData?.error?.code || 'HTTP_ERROR';
    const message = errorData?.error?.message || response.statusText || `Request failed with status ${response.status}`;
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch (e) {
    return text;
  }
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body: JSON.stringify(body) }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body: JSON.stringify(body) }),
  del: (path, options) => request(path, { ...options, method: 'DELETE' }),
};
