import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useToast } from '@/hooks/use-toast';
import { useDeleteDialogState } from './useDeleteDialogState';
import { useStudentProfileAccountHandlers } from './useStudentProfileAccountHandlers';
import { useStudentProfileAcademicHandlers } from './useStudentProfileAcademicHandlers';
import { useStudentProfileAppearanceHandlers } from './useStudentProfileAppearanceHandlers';
import { useStudentProfileDataLoader } from './useStudentProfileDataLoader';
import { useStudentProfileDerivedState } from './useStudentProfileDerivedState';
import { useStudentProfilePersonalizationHandlers } from './useStudentProfilePersonalizationHandlers';
import { useStudentProfileSaveHandler } from './useStudentProfileSaveHandler';
import { useStudentProfileState } from './useStudentProfileState';

/** Coordinate student profile state, async mutations, and derived form options. */
/**
 * React hook: student profile controller.
 */
export function useStudentProfileController() {
  const { toast } = useToast();
  const { user, logout, refreshUser } = useAuth();
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, setPreference: setLanguagePreference, language, t } = useI18n();
  const navigate = useNavigate();
  const isStudent = user?.role === 'student';
  const state = useStudentProfileState();
  const deleteDialog = useDeleteDialogState();
  const derived = useStudentProfileDerivedState({ allTags: state.allTags, language, notificationPrefs: state.notificationPrefs, personalization: state.personalization, studyLevel: state.studyLevel, university: state.university, universityCatalog: state.universityCatalog });
  useStudentProfileDataLoader({ ...state, isStudent, t, toast });
  const academic = useStudentProfileAcademicHandlers({ ...state, studyYear: state.studyYear, university: state.university, universityCatalog: state.universityCatalog });
  const save = useStudentProfileSaveHandler({ ...state, t, toast });
  const appearance = useStudentProfileAppearanceHandlers({ languagePreference, refreshUser, setLanguagePreference, setThemePreference, t, themePreference, toast });
  const personalization = useStudentProfilePersonalizationHandlers({ currentNotificationPreferences: derived.currentNotificationPreferences, currentPersonalization: derived.currentPersonalization, setNotificationPrefs: state.setNotificationPrefs, setPersonalization: state.setPersonalization, t, toast });
  const account = useStudentProfileAccountHandlers({ closeDeleteDialog: deleteDialog.closeDeleteDialog, deletePassword: deleteDialog.deletePassword, logout, navigate, t, toast });
  return { ...state, ...derived, ...deleteDialog, ...academic, ...save, ...appearance, ...personalization, ...account, isStudent, languagePreference, t, themePreference };
}
