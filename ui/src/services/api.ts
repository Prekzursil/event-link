import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { getStoredLanguagePreference, resolveLanguage } from '@/lib/language';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

type RetriableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = globalThis.localStorage.getItem('access_token');
    const headers = config.headers ?? {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    headers['Accept-Language'] = resolveLanguage(getStoredLanguagePreference());
    config.headers = headers;
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest: RetriableRequestConfig | undefined = error.config;
    if (!originalRequest) {
      throw error;
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = globalThis.localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token: newRefreshToken } = response.data;
          globalThis.localStorage.setItem('access_token', access_token);
          if (newRefreshToken) {
            globalThis.localStorage.setItem('refresh_token', newRefreshToken);
          }

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        } catch (refreshError) {
          globalThis.localStorage.removeItem('access_token');
          globalThis.localStorage.removeItem('refresh_token');
          globalThis.localStorage.removeItem('user');
          globalThis.location.href = '/login';
          throw refreshError;
        }
      }
    }

    throw error;
  }
);

export default api;
