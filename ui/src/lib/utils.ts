import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { getIntlLocale, getStoredLanguagePreference, resolveLanguage, type ResolvedLanguage } from '@/lib/language';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function getDefaultLanguage(): ResolvedLanguage {
  return resolveLanguage(getStoredLanguagePreference());
}

export function formatDate(date: string | Date, language: ResolvedLanguage = getDefaultLanguage()): string {
  return new Date(date).toLocaleDateString(getIntlLocale(language), {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDateTime(date: string | Date, language: ResolvedLanguage = getDefaultLanguage()): string {
  return new Date(date).toLocaleString(getIntlLocale(language), {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTime(date: string | Date, language: ResolvedLanguage = getDefaultLanguage()): string {
  return new Date(date).toLocaleTimeString(getIntlLocale(language), {
    hour: '2-digit',
    minute: '2-digit',
  });
}
