import { enUS, ro } from 'date-fns/locale';
import type { LanguagePreference } from '@/types';

export type ResolvedLanguage = 'ro' | 'en';

const STORAGE_KEY = 'language_preference';

export function normalizeLanguagePreference(value: unknown): LanguagePreference {
  if (value === 'ro' || value === 'en' || value === 'system') return value;
  return 'system';
}

export function getStoredLanguagePreference(): LanguagePreference {
  if (typeof window === 'undefined') return 'system';
  return normalizeLanguagePreference(window.localStorage.getItem(STORAGE_KEY));
}

export function storeLanguagePreference(preference: LanguagePreference) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, preference);
}

export function getSystemLanguage(): ResolvedLanguage {
  if (typeof navigator === 'undefined') return 'en';
  const lang = (navigator.language || 'en').toLowerCase();
  return lang.startsWith('ro') ? 'ro' : 'en';
}

export function resolveLanguage(preference: LanguagePreference): ResolvedLanguage {
  if (preference === 'system') return getSystemLanguage();
  return preference;
}

export function applyLanguagePreference(preference: LanguagePreference) {
  if (typeof document === 'undefined') return;
  const resolved = resolveLanguage(preference);
  document.documentElement.lang = resolved;
}

export function getIntlLocale(language: ResolvedLanguage): string {
  return language === 'ro' ? 'ro-RO' : 'en-US';
}

export function getDateFnsLocale(language: ResolvedLanguage) {
  return language === 'ro' ? ro : enUS;
}

