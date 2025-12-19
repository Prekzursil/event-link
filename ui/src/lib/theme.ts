import type { ThemePreference } from '@/types';

const STORAGE_KEY = 'theme_preference';

export function normalizeThemePreference(value: unknown): ThemePreference {
  if (value === 'light' || value === 'dark' || value === 'system') return value;
  return 'system';
}

export function getStoredThemePreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system';
  return normalizeThemePreference(window.localStorage.getItem(STORAGE_KEY));
}

export function storeThemePreference(preference: ThemePreference) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, preference);
}

export function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light';
}

export function resolveTheme(preference: ThemePreference): 'light' | 'dark' {
  if (preference === 'system') return getSystemTheme();
  return preference;
}

export function applyThemePreference(preference: ThemePreference) {
  if (typeof document === 'undefined') return;
  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
}

export function subscribeToSystemThemeChanges(onResolvedThemeChange: (theme: 'light' | 'dark') => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};

  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = () => onResolvedThemeChange(media.matches ? 'dark' : 'light');

  if (media.addEventListener) {
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }

  // Safari < 14
  media.addListener(handler);
  return () => media.removeListener(handler);
}
