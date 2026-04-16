import { useCallback, useState } from 'react';
import authService from '@/services/auth.service';
import type { LanguagePreference, ThemePreference } from '@/types';
import {
  type RefreshUser,
  type SetLanguagePreference,
  type SetThemePreference,
  type ToastFn,
  type TranslationStrings,
} from './studentProfileController.shared';

type AppearanceHandlerArgs = Readonly<{
  languagePreference: LanguagePreference;
  refreshUser: RefreshUser;
  setLanguagePreference: SetLanguagePreference;
  setThemePreference: SetThemePreference;
  t: TranslationStrings;
  themePreference: ThemePreference;
  toast: ToastFn;
}>;

/** Persist language and theme preference changes with optimistic UI updates. */
/**
 * React hook: student profile appearance handlers.
 */
export function useStudentProfileAppearanceHandlers({
  languagePreference,
  refreshUser,
  setLanguagePreference,
  setThemePreference,
  t,
  themePreference,
  toast,
}: AppearanceHandlerArgs) {
  const [isSavingTheme, setIsSavingTheme] = useState<boolean>(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState<boolean>(false);

  const handleThemeChange = useCallback(async (nextPreference: ThemePreference) => {
    const previous = themePreference;
    setThemePreference(nextPreference);
    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
      toast({ title: t.theme.savedTitle, description: t.theme.savedDescription });
    } catch {
      setThemePreference(previous);
      toast({ title: t.theme.saveErrorTitle, description: t.theme.saveErrorDescription, variant: 'destructive' });
    } finally {
      setIsSavingTheme(false);
    }
  }, [refreshUser, setThemePreference, t, themePreference, toast]);

  const handleLanguageChange = useCallback(async (nextPreference: LanguagePreference) => {
    const previous = languagePreference;
    setLanguagePreference(nextPreference);
    setIsSavingLanguage(true);
    try {
      await authService.updateLanguagePreference(nextPreference);
      await refreshUser();
      toast({ title: t.language.savedTitle, description: t.language.savedDescription });
    } catch {
      setLanguagePreference(previous);
      toast({ title: t.language.saveErrorTitle, description: t.language.saveErrorDescription, variant: 'destructive' });
    } finally {
      setIsSavingLanguage(false);
    }
  }, [languagePreference, refreshUser, setLanguagePreference, t, toast]);

  return {
    handleLanguageChange,
    handleThemeChange,
    isSavingLanguage,
    isSavingTheme,
  };
}
