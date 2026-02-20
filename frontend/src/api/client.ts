import axios from "axios";
import { API_BASE_URL } from "../lib/constants";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Extract a human-readable error message from an Axios error response.
 */
function extractErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "An unexpected error occurred";

  const data = error.response?.data;
  if (!data) {
    if (error.code === "ERR_NETWORK") return "Network error — is the server running?";
    if (error.code === "ECONNABORTED") return "Request timed out";
    return error.message || "An unexpected error occurred";
  }

  // FastAPI returns { detail: string } or { detail: string, errors: [...] }
  if (typeof data.detail === "string") return data.detail;

  // Validation errors: { detail: "Validation error", errors: [...] }
  if (data.errors && Array.isArray(data.errors)) {
    return data.errors
      .map((e: { field?: string; message?: string }) =>
        e.field ? `${e.field}: ${e.message}` : e.message
      )
      .join("; ");
  }

  return "An unexpected error occurred";
}

/**
 * Simple event bus for API errors — allows React components to subscribe
 * without coupling the Axios client to React context.
 */
type ErrorListener = (message: string, status: number | undefined) => void;
const errorListeners: Set<ErrorListener> = new Set();

export function onApiError(listener: ErrorListener): () => void {
  errorListeners.add(listener);
  return () => errorListeners.delete(listener);
}

function notifyError(message: string, status: number | undefined) {
  errorListeners.forEach((fn) => fn(message, status));
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 — try refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");

      if (refreshToken) {
        try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          localStorage.setItem("access_token", res.data.access_token);
          localStorage.setItem("refresh_token", res.data.refresh_token);
          originalRequest.headers.Authorization = `Bearer ${res.data.access_token}`;
          return client(originalRequest);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      } else {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }

    // Notify listeners about the error (skip 401 since they redirect to login)
    if (error.response?.status !== 401) {
      const message = extractErrorMessage(error);
      notifyError(message, error.response?.status);
    }

    return Promise.reject(error);
  }
);

export default client;
