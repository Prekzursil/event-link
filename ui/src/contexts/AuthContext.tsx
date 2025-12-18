import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '@/types';
import authService from '@/services/auth.service';
import { useTheme } from '@/contexts/ThemeContext';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isOrganizer: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, confirmPassword: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { setPreference: setThemePreference } = useTheme();

  const refreshUser = useCallback(async () => {
    try {
      if (authService.isAuthenticated()) {
        const userData = await authService.getMe();
        setUser(userData);
        if (userData.theme_preference) {
          setThemePreference(userData.theme_preference);
        }
      }
    } catch {
      authService.logout();
      setUser(null);
    }
  }, [setThemePreference]);

  useEffect(() => {
    const initAuth = async () => {
      await refreshUser();
      setIsLoading(false);
    };
    initAuth();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    await authService.login({ email, password });
    await refreshUser();
  };

  const register = async (email: string, password: string, confirmPassword: string, fullName?: string) => {
    await authService.register({
      email,
      password,
      confirm_password: confirmPassword,
      full_name: fullName,
    });
    await refreshUser();
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isOrganizer: user?.role === 'organizator',
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
