/**
 * auth.js
 * ───────
 * Minimal JWT token store + axios interceptor.
 * Tokens are persisted in localStorage so they survive page refresh.
 *
 * Usage:
 *   import { login, logout, getUser, setupAxios } from './auth';
 *   setupAxios(axiosInstance);          // call once in index.js
 *   await login('admin', 'Admin1234!'); // stores tokens
 *   const { username, role } = getUser();
 */

import axios from 'axios';

const ACCESS_KEY  = 'sc_access';
const REFRESH_KEY = 'sc_refresh';

// ── token helpers ─────────────────────────────────────────────────────────

export function saveTokens(access, refresh) {
  localStorage.setItem(ACCESS_KEY,  access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken()  { return localStorage.getItem(ACCESS_KEY);  }
export function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }

function _decodeJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

function _isExpired(token, skewSec = 30) {
  const payload = _decodeJwt(token);
  if (!payload || !payload.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= (now + skewSec);
}

export function isAuthenticated() {
  const access = getAccessToken();
  const refresh = getRefreshToken();
  if (!access || !refresh) return false;
  if (_isExpired(refresh)) {
    clearTokens();
    return false;
  }
  return !_isExpired(access);
}

/**
 * Restore session silently on app boot:
 * - if access is valid => keep it
 * - if access expired but refresh valid => refresh once
 * - if refresh invalid => clear tokens
 */
export async function restoreSession() {
  const access = getAccessToken();
  const refresh = getRefreshToken();

  if (!access || !refresh) {
    clearTokens();
    return null;
  }
  if (_isExpired(refresh)) {
    clearTokens();
    return null;
  }
  if (!_isExpired(access)) {
    return getUser();
  }

  try {
    const r = await axios.post('/api/auth/token/refresh/', { refresh });
    saveTokens(r.data.access, refresh);
    return getUser();
  } catch {
    clearTokens();
    return null;
  }
}

/** Decode JWT payload (base64url → JSON) — no signature verification needed client-side. */
export function getUser() {
  const token = getAccessToken();
  if (!token) return null;
  const payload = _decodeJwt(token);
  if (!payload) {
    return null;
  }
  return { user_id: payload.user_id, role: payload.role, full_name: payload.full_name };
}

// ── login / logout ────────────────────────────────────────────────────────

/** POST /api/auth/token/ → stores tokens → returns user payload */
export async function login(username, password) {
  const res = await axios.post('/api/auth/token/', { username, password });
  saveTokens(res.data.access, res.data.refresh);
  return getUser();
}

/** Clear tokens and optionally notify caller so UI can redirect to login. */
export function logout() {
  clearTokens();
}

// ── axios interceptors ────────────────────────────────────────────────────

/**
 * Call once: attaches Authorization header to every request
 * and handles 401 → token refresh → retry (one attempt only).
 */
export function setupAxios(axiosInstance) {
  // REQUEST → attach access token
  axiosInstance.interceptors.request.use(
    (config) => {
      const token = getAccessToken();
      if (token) config.headers['Authorization'] = `Bearer ${token}`;
      return config;
    },
    (err) => Promise.reject(err),
  );

  // RESPONSE → on 401 try to refresh, then retry original request once
  let isRefreshing = false;
  let pendingQueue = [];

  const processQueue = (error, token = null) => {
    pendingQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)));
    pendingQueue = [];
  };

  axiosInstance.interceptors.response.use(
    (res) => res,
    async (error) => {
      const original = error.config;
      if (error.response?.status !== 401 || original._retry) {
        return Promise.reject(error);
      }
      const refresh = getRefreshToken();
      if (!refresh) {
        clearTokens();
        return Promise.reject(error);
      }
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingQueue.push({ resolve, reject });
        }).then((token) => {
          original.headers['Authorization'] = `Bearer ${token}`;
          return axiosInstance(original);
        });
      }
      original._retry = true;
      isRefreshing = true;
      try {
        const r = await axios.post('/api/auth/token/refresh/', { refresh });
        saveTokens(r.data.access, getRefreshToken());
        processQueue(null, r.data.access);
        original.headers['Authorization'] = `Bearer ${r.data.access}`;
        return axiosInstance(original);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        clearTokens();
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    },
  );
}
