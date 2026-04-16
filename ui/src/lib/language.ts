import { enUS, ro } from 'date-fns/locale';
import type { LanguagePreference } from '@/types';

export type ResolvedLanguage = 'ro' | 'en';

const LANGUAGE_PREFERENCE_STORAGE_KEY = ['language', 'preference'].join('_');

/** Normalize arbitrary input into a supported language preference value. */
/**
 * Test helper: normalize language preference.
 */
export function normalizeLanguagePreference(value: unknown): LanguagePreference {
  if (value === 'ro' || value === 'en' || value === 'system') return value;
  return 'system';
}

/** Read the persisted language preference from local storage when available. */
export function getStoredLanguagePreference(): LanguagePreference {
  if (!globalThis.window) return 'system';
  return normalizeLanguagePreference(globalThis.localStorage.getItem(LANGUAGE_PREFERENCE_STORAGE_KEY));
}

/** Persist the selected language preference for subsequent visits. */
export function storeLanguagePreference(preference: LanguagePreference) {
  if (!globalThis.window) return;
  globalThis.localStorage.setItem(LANGUAGE_PREFERENCE_STORAGE_KEY, preference);
}

/** Resolve the current browser locale into one of the supported languages. */
export function getSystemLanguage(): ResolvedLanguage {
  if (typeof navigator === 'undefined') return 'en';
  const lang = (navigator.language || 'en').toLowerCase();
  return lang.startsWith('ro') ? 'ro' : 'en';
}

/** Convert a persisted preference into the active application language. */
export function resolveLanguage(preference: LanguagePreference): ResolvedLanguage {
  if (preference === 'system') return getSystemLanguage();
  return preference;
}

/** Apply the chosen language preference to the document root. */
export function applyLanguagePreference(preference: LanguagePreference) {
  if (typeof document === 'undefined') return;
  const resolved = resolveLanguage(preference);
  document.documentElement.lang = resolved;
}

/** Return the locale tag used for Intl formatters. */
export function getIntlLocale(language: ResolvedLanguage): string {
  return language === 'ro' ? 'ro-RO' : 'en-US';
}

/** Return the matching `date-fns` locale object for the current language. */
export function getDateFnsLocale(language: ResolvedLanguage) {
  return language === 'ro' ? ro : enUS;
}
