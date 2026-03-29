import { createContext, useContext, useState, useEffect, useCallback, useMemo, type ReactNode } from 'react';
import type { User } from '@/types';
import authService from '@/services/auth.service';
import { useTheme } from '@/contexts/ThemeContext';
import { useI18n } from '@/contexts/LanguageContext';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isOrganizer: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, confirmPassword: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { setPreference: setThemePreference } = useTheme();
  const { setPreference: setLanguagePreference } = useI18n();

  const refreshUser = useCallback(async () => {
    try {
      if (authService.isAuthenticated()) {
        const userData = await authService.getMe();
        setUser(userData);
        if (userData.theme_preference) {
          setThemePreference(userData.theme_preference);
        }
        if (userData.language_preference) {
          setLanguagePreference(userData.language_preference);
        }
      }
    } catch {
      authService.logout();
      setUser(null);
    }
  }, [setLanguagePreference, setThemePreference]);

  useEffect(() => {
    const initAuth = async () => {
      await refreshUser();
      setIsLoading(false);
    };
    initAuth();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    await authService.login({ email, password });
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (email: string, password: string, confirmPassword: string, fullName?: string) => {
    await authService.register({
      email,
      password,
      confirm_password: confirmPassword,
      full_name: fullName,
    });
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isOrganizer: user?.role === 'organizator' || user?.role === 'admin',
      isAdmin: user?.role === 'admin',
      isLoading,
      login,
      register,
      logout,
      refreshUser,
    }),
    [isLoading, login, logout, refreshUser, register, user],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
