import { createContext, useContext, useState, useCallback, useMemo } from 'react';

const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

function createApiClient() {
  const request = async (method, path, body = null, opts = {}) => {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    if (opts.idempotent) headers['X-Idempotency-Key'] = opts.idempotencyKey || `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    
    const res = await fetch(`${API_BASE}${path}`, {
      method, credentials: 'include', headers,
      body: body ? JSON.stringify(body) : null,
    });
    
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) throw new AuthError(data.message || 'Sesi berakhir. Silakan login kembali.');
      if (res.status === 403) throw new ForbiddenError(data.message || 'Anda tidak memiliki izin untuk aksi ini.');
      if (res.status === 422) throw new ValidationError(data.message || 'Validasi gagal', data.errors);
      throw new ApiError(data.message || 'Terjadi kesalahan pada server', res.status);
    }
    return data;
  };
  
  return {
    get: (path, h) => request('GET', path, null, h ? { headers: h } : {}),
    post: (path, body, opts) => request('POST', path, body, opts || {}),
    put: (path, body, opts) => request('PUT', path, body, opts || {}),
    delete: (path, opts) => request('DELETE', path, null, opts || {}),
  };
}

export class ApiError extends Error {
  constructor(msg, status) { super(msg); this.name = 'ApiError'; this.status = status; }
}
export class AuthError extends ApiError { constructor(msg) { super(msg, 401); this.name = 'AuthError'; } }
export class ForbiddenError extends ApiError { constructor(msg) { super(msg, 403); this.name = 'ForbiddenError'; } }
export class ValidationError extends ApiError {
  constructor(msg, errors) { super(msg, 422); this.name = 'ValidationError'; this.errors = errors || {}; }
}

const ApiContext = createContext(null);
export function ApiProvider({ children }) {
  const api = useMemo(() => createApiClient(), []);
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}
export function useApi() { return useContext(ApiContext); }