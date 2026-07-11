import axios, { AxiosError } from "axios";

// Base URL: VITE_API_BASE in production; empty string in dev so the Vite proxy
// (/api -> backend) handles it.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const TOKEN_KEY = "aegis_access_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Typed application error surfaced to the UI. */
export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 120_000, // long for large docs; SSE uses its own path
  headers: { Accept: "application/json" },
});

// Attach the bearer token to every request.
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Normalize errors into ApiError, and drop the session on 401.
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail =
      (error.response?.data as { detail?: string } | undefined)?.detail ??
      error.message ??
      "Request failed";

    if (status === 401) {
      clearToken();
    }
    return Promise.reject(new ApiError(String(detail), status));
  },
);

/** Decode the JWT payload without verifying (client-side display only). */
export function decodeJwt(
  token: string,
): { sub?: string; role?: string; exp?: number } | null {
  try {
    const part = token.split(".")[1];
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}
