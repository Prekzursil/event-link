import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  applyLanguagePreference,
  getDateFnsLocale,
  getIntlLocale,
  getStoredLanguagePreference,
  getSystemLanguage,
  normalizeLanguagePreference,
  resolveLanguage,
  storeLanguagePreference,
} from '@/lib/language';
import {
  applyThemePreference,
  getStoredThemePreference,
  getSystemTheme,
  normalizeThemePreference,
  resolveTheme,
  storeThemePreference,
  subscribeToSystemThemeChanges,
} from '@/lib/theme';
import { cn, formatDate, formatDateTime, formatTime } from '@/lib/utils';
import { EVENT_CATEGORIES, getEventCategoryLabel } from '@/lib/eventCategories';

describe('lib helpers', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = 'en';
    document.documentElement.className = '';
    document.documentElement.style.colorScheme = '';
  });

  it('covers language normalization and storage flow', () => {
    expect(normalizeLanguagePreference('ro')).toBe('ro');
    expect(normalizeLanguagePreference('en')).toBe('en');
    expect(normalizeLanguagePreference('system')).toBe('system');
    expect(normalizeLanguagePreference('invalid')).toBe('system');

    storeLanguagePreference('ro');
    expect(getStoredLanguagePreference()).toBe('ro');
    expect(resolveLanguage('en')).toBe('en');
    expect(['ro', 'en']).toContain(getSystemLanguage());

    applyLanguagePreference('ro');
    expect(document.documentElement.lang).toBe('ro');

    expect(getIntlLocale('ro')).toBe('ro-RO');
    expect(getIntlLocale('en')).toBe('en-US');
    expect(getDateFnsLocale('ro')).toBeDefined();
    expect(getDateFnsLocale('en')).toBeDefined();
  });

  it('covers theme normalization and media subscription variants', () => {
    expect(normalizeThemePreference('light')).toBe('light');
    expect(normalizeThemePreference('dark')).toBe('dark');
    expect(normalizeThemePreference('system')).toBe('system');
    expect(normalizeThemePreference('x')).toBe('system');

    storeThemePreference('dark');
    expect(getStoredThemePreference()).toBe('dark');
    expect(resolveTheme('dark')).toBe('dark');

    const matchMediaMock = vi.fn();
    Object.defineProperty(globalThis, 'matchMedia', {
      value: matchMediaMock,
      configurable: true,
      writable: true,
    });

    const modernAdd = vi.fn();
    const modernRemove = vi.fn();
    matchMediaMock.mockReturnValue({
      matches: true,
      addEventListener: modernAdd,
      removeEventListener: modernRemove,
    });
    expect(getSystemTheme()).toBe('dark');

    applyThemePreference('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');

    const modernCallback = vi.fn();
    const unsubscribeModern = subscribeToSystemThemeChanges(modernCallback);
    const modernHandler = modernAdd.mock.calls[0][1] as () => void;
    modernHandler();
    expect(modernCallback).toHaveBeenCalledWith('dark');
    unsubscribeModern();
    expect(modernRemove).toHaveBeenCalledWith('change', modernHandler);

    const legacyMedia = {
      matches: false,
      onchange: null as ((this: MediaQueryList, ev: MediaQueryListEvent) => void) | null,
    };
    matchMediaMock.mockReturnValueOnce(legacyMedia as MediaQueryList);

    const legacyCallback = vi.fn();
    const unsubscribeLegacy = subscribeToSystemThemeChanges(legacyCallback);
    const legacyHandler = legacyMedia.onchange;
    expect(typeof legacyHandler).toBe('function');
    legacyHandler?.call(legacyMedia as MediaQueryList, new Event('change') as MediaQueryListEvent);
    expect(legacyCallback).toHaveBeenCalledWith('light');
    unsubscribeLegacy();
    expect(legacyMedia.onchange).toBeNull();
  });

  it('covers language and theme guards outside browser globals', () => {
    const originalWindow = globalThis.window;
    const originalDocument = globalThis.document;
    const originalNavigator = globalThis.navigator;

    Object.defineProperty(globalThis, 'window', { configurable: true, value: undefined });
    Object.defineProperty(globalThis, 'document', { configurable: true, value: undefined });
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: undefined });

    expect(getStoredLanguagePreference()).toBe('system');
    expect(getSystemLanguage()).toBe('en');
    expect(getStoredThemePreference()).toBe('system');
    expect(getSystemTheme()).toBe('light');
    expect(subscribeToSystemThemeChanges(() => undefined)()).toBeUndefined();

    expect(() => storeLanguagePreference('en')).not.toThrow();
    expect(() => applyLanguagePreference('en')).not.toThrow();
    expect(() => storeThemePreference('dark')).not.toThrow();
    expect(() => applyThemePreference('dark')).not.toThrow();

    Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
    Object.defineProperty(globalThis, 'document', { configurable: true, value: originalDocument });
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator });

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { language: 'en-US' },
    });
    expect(getSystemLanguage()).toBe('en');

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { language: '' },
    });
    expect(getSystemLanguage()).toBe('en');

    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { language: 'ro-RO' },
    });
    expect(getSystemLanguage()).toBe('ro');

    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator });
  });

  it('covers formatting utilities and category label lookup', () => {
    expect(cn('a', undefined, 'c')).toContain('a');

    const value = '2026-01-01T10:20:00.000Z';
    expect(formatDate(value)).toContain('2026');
    expect(formatDate(value, 'en')).toContain('2026');
    expect(formatDateTime(value, 'en')).toContain('2026');
    expect(formatTime(value, 'en')).toContain(':');

    expect(EVENT_CATEGORIES.length).toBeGreaterThan(0);
    expect(getEventCategoryLabel('Technical', 'ro')).toBe('Tehnic');
    expect(getEventCategoryLabel('Technical', 'en')).toBe('Technical');
    expect(getEventCategoryLabel('Unknown', 'en')).toBe('Unknown');
    expect(getEventCategoryLabel(undefined, 'en')).toBeUndefined();
  });
});
