import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { ThemePreference } from '@/types';
import {
  applyThemePreference,
  getStoredThemePreference,
  resolveTheme,
  storeThemePreference,
  subscribeToSystemThemeChanges,
} from '@/lib/theme';

interface ThemeContextType {
  preference: ThemePreference;
  resolvedTheme: 'light' | 'dark';
  setPreference: (preference: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

/** Provide the active theme preference and resolved theme to the app. */
export function ThemeProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [preference, setPreference] = useState<ThemePreference>(() => getStoredThemePreference());
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>(() => resolveTheme(getStoredThemePreference()));

  useEffect(() => {
    storeThemePreference(preference);
    applyThemePreference(preference);
    setResolvedTheme(resolveTheme(preference));
  }, [preference]);

  useEffect(() => {
    if (preference !== 'system') {
      return undefined;
    }
    return subscribeToSystemThemeChanges((theme) => {
      setResolvedTheme(theme);
      applyThemePreference('system');
    });
  }, [preference]);

  const value = useMemo(
    () => ({
      preference,
      resolvedTheme,
      setPreference,
    }),
    [preference, resolvedTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/** Read the current theme context. */
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return ctx;
}
