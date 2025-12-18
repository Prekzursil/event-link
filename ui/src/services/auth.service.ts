import api from './api';
import type { AuthToken, User, ThemePreference } from '../types';

export interface RegisterData {
  email: string;
  password: string;
  confirm_password: string;
  full_name?: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export const authService = {
  async register(data: RegisterData): Promise<AuthToken> {
    const response = await api.post<AuthToken>('/register', data);
    this.setTokens(response.data);
    return response.data;
  },

  async login(data: LoginData): Promise<AuthToken> {
    const response = await api.post<AuthToken>('/login', data);
    this.setTokens(response.data);
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await api.get<User>('/me');
    return response.data;
  },

  async updateThemePreference(themePreference: ThemePreference): Promise<User> {
    const response = await api.put<User>('/api/me/theme', { theme_preference: themePreference });
    return response.data;
  },

  async requestPasswordReset(email: string): Promise<void> {
    await api.post('/password/forgot', { email });
  },

  async resetPassword(token: string, newPassword: string, confirmPassword: string): Promise<void> {
    await api.post('/password/reset', {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  },

  setTokens(data: AuthToken): void {
    localStorage.setItem('access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }
    localStorage.setItem('user', JSON.stringify({
      id: data.user_id,
      role: data.role,
    }));
  },

  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },

  getStoredUser(): { id: number; role: string } | null {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  },

  isOrganizer(): boolean {
    const user = this.getStoredUser();
    return user?.role === 'organizator' || user?.role === 'admin';
  },
};

export default authService;
