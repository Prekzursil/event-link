import type { ThemePreference } from '@/types';

const THEME_PREFERENCE_STORAGE_KEY = ['theme', 'preference'].join('_');

/** Normalize arbitrary input into a supported theme preference value. */
export function normalizeThemePreference(value: unknown): ThemePreference {
  if (value === 'light' || value === 'dark' || value === 'system') return value;
  return 'system';
}

/** Read the persisted theme preference from local storage when available. */
export function getStoredThemePreference(): ThemePreference {
  if (!globalThis.window) return 'system';
  return normalizeThemePreference(globalThis.localStorage.getItem(THEME_PREFERENCE_STORAGE_KEY));
}

/** Persist the selected theme preference for subsequent visits. */
export function storeThemePreference(preference: ThemePreference) {
  if (!globalThis.window) return;
  globalThis.localStorage.setItem(THEME_PREFERENCE_STORAGE_KEY, preference);
}

/** Resolve the browser color-scheme preference when needed. */
export function getSystemTheme(): 'light' | 'dark' {
  const browserWindow = globalThis.window;
  if (!browserWindow) return 'light';
  return browserWindow.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light';
}

/** Convert a persisted theme preference into the active document theme. */
export function resolveTheme(preference: ThemePreference): 'light' | 'dark' {
  if (preference === 'system') return getSystemTheme();
  return preference;
}

/** Apply the chosen theme preference to the document root. */
export function applyThemePreference(preference: ThemePreference) {
  if (typeof document === 'undefined') return;
  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
}

export function subscribeToSystemThemeChanges(onResolvedThemeChange: (theme: 'light' | 'dark') => void) {
  const browserWindow = globalThis.window;
  if (!browserWindow?.matchMedia) return () => {};

  const media = browserWindow.matchMedia('(prefers-color-scheme: dark)');
  const handler = () => onResolvedThemeChange(media.matches ? 'dark' : 'light');

  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }

  const previousOnChange = media.onchange;
  media.onchange = handler;
  return () => {
    media.onchange = previousOnChange;
  };
}
