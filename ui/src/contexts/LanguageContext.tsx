import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { LanguagePreference } from '@/types';
import {
  applyLanguagePreference,
  getStoredLanguagePreference,
  resolveLanguage,
  storeLanguagePreference,
  type ResolvedLanguage,
} from '@/lib/language';
import { UI_STRINGS, type UiStrings } from '@/i18n/strings';

interface LanguageContextType {
  preference: LanguagePreference;
  language: ResolvedLanguage;
  t: UiStrings;
  setPreference: (preference: LanguagePreference) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<LanguagePreference>(() => getStoredLanguagePreference());
  const [language, setLanguage] = useState<ResolvedLanguage>(() => resolveLanguage(getStoredLanguagePreference()));

  useEffect(() => {
    storeLanguagePreference(preference);
    applyLanguagePreference(preference);
    setLanguage(resolveLanguage(preference));
  }, [preference]);

  const value = useMemo(
    () => ({
      preference,
      language,
      t: UI_STRINGS[language],
      setPreference,
    }),
    [preference, language],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error('useI18n must be used within a LanguageProvider');
  }
  return ctx;
}

