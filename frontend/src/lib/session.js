import { decodeToken, isExpired } from './jwt.js';

let logoutTimer = null;

export function getToken() {
  const token = sessionStorage.getItem('access_token');
  if (!token || isExpired(token)) {
    clearSession();
    return null;
  }
  return token;
}

export function setToken(token) {
  if (!token) {
    clearSession();
    return;
  }
  sessionStorage.setItem('access_token', token);
}

export function clearSession() {
  sessionStorage.removeItem('access_token');
  if (logoutTimer) {
    clearTimeout(logoutTimer);
    logoutTimer = null;
  }
}

export function getUser() {
  const token = getToken();
  if (!token) return null;
  const decoded = decodeToken(token);
  if (!decoded) return null;
  return {
    id: decoded.sub,
    role: decoded.role,
    exp: decoded.exp,
  };
}

export function setupAutoLogout(onLogout) {
  if (logoutTimer) {
    clearTimeout(logoutTimer);
    logoutTimer = null;
  }
  const token = sessionStorage.getItem('access_token');
  if (!token) return;
  const decoded = decodeToken(token);
  if (!decoded || !decoded.exp) return;

  const nowInMs = Date.now();
  const expInMs = decoded.exp * 1000;
  const timeoutMs = expInMs - nowInMs;

  if (timeoutMs <= 0) {
    clearSession();
    if (onLogout) onLogout();
  } else {
    logoutTimer = setTimeout(() => {
      clearSession();
      if (onLogout) onLogout();
    }, timeoutMs);
  }
}
