import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import authService from '@/services/auth.service';
import eventService from '@/services/event.service';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useI18n } from '@/contexts/LanguageContext';
import type {
  LanguagePreference,
  NotificationPreferences,
  PersonalizationSettings,
  StudyLevel,
  Tag,
  StudentProfile,
  ThemePreference,
  UniversityCatalogItem,
} from '@/types';
import { MAX_YEARS_BY_LEVEL } from './shared';

export function useStudentProfileController() {
  const { toast } = useToast();
  const { user, logout, refreshUser } = useAuth();
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, setPreference: setLanguagePreference, language, t } = useI18n();
  const navigate = useNavigate();
  const isStudent = user?.role === 'student';
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSavingTheme, setIsSavingTheme] = useState(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState(false);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [universityCatalog, setUniversityCatalog] = useState<UniversityCatalogItem[]>([]);
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [city, setCity] = useState('');
  const [university, setUniversity] = useState('');
  const [faculty, setFaculty] = useState('');
  const [studyLevel, setStudyLevel] = useState<StudyLevel | ''>('');
  const [studyYear, setStudyYear] = useState<number | undefined>();
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [personalization, setPersonalization] = useState<PersonalizationSettings | null>(null);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPreferences | null>(null);
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

  const musicInterestNames = useMemo(
    () =>
      new Set([
        'Muzică',
        'Rock',
        'Pop',
        'Hip-Hop',
        'EDM',
        'Jazz',
        'Clasică',
        'Folk',
        'Metal',
      ]),
    [],
  );

  const musicTags = useMemo(
    () => allTags.filter((tag) => musicInterestNames.has(tag.name)),
    [allTags, musicInterestNames],
  );
  const otherTags = useMemo(
    () => allTags.filter((tag) => !musicInterestNames.has(tag.name)),
    [allTags, musicInterestNames],
  );
  const selectedUniversity = useMemo(() => {
    const normalized = university.trim().toLowerCase();
    if (!normalized) {
      return null;
    }
    return universityCatalog.find((item) => item.name.toLowerCase() === normalized) ?? null;
  }, [university, universityCatalog]);
  const facultyOptions = useMemo(() => selectedUniversity?.faculties ?? [], [selectedUniversity]);
  const hiddenTags = personalization?.hidden_tags ?? [];
  const blockedOrganizers = personalization?.blocked_organizers ?? [];
  const cityOptions = useMemo(() => {
    const options = new Set<string>();
    for (const item of universityCatalog) {
      if (item.city) {
        options.add(item.city);
      }
    }
    return Array.from(options).sort((left, right) => left.localeCompare(right, language));
  }, [language, universityCatalog]);
  const studyYearOptions = useMemo(() => {
    if (!studyLevel) {
      return [];
    }
    const max = MAX_YEARS_BY_LEVEL[studyLevel];
    return Array.from({ length: max }, (_, idx) => idx + 1);
  }, [studyLevel]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [profileData, tagsData] = await Promise.all([
        eventService.getStudentProfile(),
        eventService.getAllTags(),
      ]);
      setProfile(profileData);
      setFullName(profileData.full_name ?? '');
      setCity(profileData.city ?? '');
      setUniversity(profileData.university ?? '');
      setFaculty(profileData.faculty ?? '');
      setStudyLevel(profileData.study_level ?? '');
      setStudyYear(profileData.study_year ?? undefined);
      setSelectedTagIds(profileData.interest_tags.map((tag) => tag.id));
      setAllTags(tagsData);

      if (isStudent) {
        const [personalizationData, notificationData] = await Promise.all([
          eventService.getPersonalizationSettings().catch(() => ({ hidden_tags: [], blocked_organizers: [] })),
          eventService.getNotificationPreferences().catch(() => ({
            email_digest_enabled: false,
            email_filling_fast_enabled: false,
          })),
        ]);
        setPersonalization(personalizationData);
        setNotificationPrefs(notificationData);
      } else {
        setPersonalization(null);
        setNotificationPrefs(null);
      }

      try {
        const catalog = await eventService.getUniversityCatalog();
        setUniversityCatalog(catalog);
      } catch {
        setUniversityCatalog([]);
      }
    } catch {
      toast({
        title: t.profile.loadErrorTitle,
        description: t.profile.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [isStudent, t, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!deleteDialogOpen) {
      setDeletePassword('');
    }
  }, [deleteDialogOpen]);

  const handleTagToggle = useCallback((tagId: number) => {
    setSelectedTagIds((previous) => (
      previous.includes(tagId)
        ? previous.filter((id) => id !== tagId)
        : [...previous, tagId]
    ));
  }, []);

  const handleUniversityChange = useCallback((nextUniversity: string) => {
    const normalized = nextUniversity.trim().toLowerCase();
    const match = universityCatalog.find((item) => item.name.toLowerCase() === normalized);
    setUniversity(nextUniversity);
    if (nextUniversity !== university) {
      setFaculty('');
    }
    const matchedCity = typeof match?.city === 'string' && match.city.trim() ? match.city : '';
    if (matchedCity) {
      setCity((previousCity) => (previousCity.trim() ? previousCity : matchedCity));
    }
  }, [university, universityCatalog]);

  const handleStudyLevelChange = useCallback((value: string) => {
    const next = value as StudyLevel;
    setStudyLevel(next);
    const max = MAX_YEARS_BY_LEVEL[next];
    if (typeof studyYear === 'number' && (studyYear < 1 || studyYear > max)) {
      setStudyYear(undefined);
    }
  }, [studyYear]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const updatedProfile = await eventService.updateStudentProfile({
        full_name: fullName.trim() ? fullName.trim() : undefined,
        city: city.trim(),
        university: university.trim(),
        faculty: faculty.trim(),
        study_level: studyLevel || undefined,
        study_year: typeof studyYear === 'number' ? studyYear : undefined,
        interest_tag_ids: selectedTagIds,
      });
      setProfile(updatedProfile);
      setFullName(updatedProfile.full_name ?? '');
      setCity(updatedProfile.city ?? '');
      setUniversity(updatedProfile.university ?? '');
      setFaculty(updatedProfile.faculty ?? '');
      setStudyLevel(updatedProfile.study_level ?? '');
      setStudyYear(updatedProfile.study_year ?? undefined);
      toast({
        title: t.profile.saveSuccessTitle,
        description: t.profile.saveSuccessDescription,
      });
    } catch {
      toast({
        title: t.profile.saveErrorTitle,
        description: t.profile.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  }, [city, faculty, fullName, selectedTagIds, studyLevel, studyYear, t, toast, university]);

  const handleThemeChange = useCallback(async (nextPreference: ThemePreference) => {
    const previous = themePreference;
    setThemePreference(nextPreference);
    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
      toast({
        title: t.theme.savedTitle,
        description: t.theme.savedDescription,
      });
    } catch {
      setThemePreference(previous);
      toast({
        title: t.theme.saveErrorTitle,
        description: t.theme.saveErrorDescription,
        variant: 'destructive',
      });
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
      toast({
        title: t.language.savedTitle,
        description: t.language.savedDescription,
      });
    } catch {
      setLanguagePreference(previous);
      toast({
        title: t.language.saveErrorTitle,
        description: t.language.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingLanguage(false);
    }
  }, [languagePreference, refreshUser, setLanguagePreference, t, toast]);

  const handleNotificationPreferenceChange = useCallback(async (
    patch: Partial<NotificationPreferences>,
  ) => {
    const previous = notificationPrefs!;
    const next = { ...previous, ...patch };
    setNotificationPrefs(next);
    setIsSavingNotifications(true);
    try {
      const saved = await eventService.updateNotificationPreferences(patch);
      setNotificationPrefs(saved);
      toast({
        title: t.notifications.savedTitle,
        description: t.notifications.savedDescription,
      });
    } catch {
      setNotificationPrefs(previous);
      toast({
        title: t.common.error,
        description: t.notifications.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingNotifications(false);
    }
  }, [notificationPrefs, t, toast]);

  const handleUnhideTag = useCallback(async (tagId: number) => {
    const currentPersonalization = personalization!;
    try {
      await eventService.unhideTag(tagId);
      setPersonalization({
        ...currentPersonalization,
        hidden_tags: currentPersonalization.hidden_tags.filter((tag) => tag.id !== tagId),
      });
      toast({
        title: t.personalization.tagUnhiddenTitle,
        description: t.personalization.tagUnhiddenDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.tagUnhiddenErrorFallback,
        variant: 'destructive',
      });
    }
  }, [personalization, t, toast]);

  const handleUnblockOrganizer = useCallback(async (organizerId: number) => {
    const currentPersonalization = personalization!;
    try {
      await eventService.unblockOrganizer(organizerId);
      setPersonalization({
        ...currentPersonalization,
        blocked_organizers: currentPersonalization.blocked_organizers.filter((org) => org.id !== organizerId),
      });
      toast({
        title: t.personalization.organizerUnblockedTitle,
        description: t.personalization.organizerUnblockedDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.organizerUnblockedErrorFallback,
        variant: 'destructive',
      });
    }
  }, [personalization, t, toast]);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    try {
      const blob = await eventService.exportMyData();
      const url = globalThis.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `eventlink-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      globalThis.URL.revokeObjectURL(url);
      toast({
        title: t.profile.exportGeneratedTitle,
        description: t.profile.exportGeneratedDescription,
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      toast({
        title: t.profile.exportErrorTitle,
        description: t.profile.exportErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsExporting(false);
    }
  }, [t, toast]);

  const closeDeleteDialog = useCallback(() => {
    setDeleteDialogOpen(false);
  }, []);

  const handleDeleteAccount = useCallback(async () => {
    const password = deletePassword.trim();
    if (!password) {
      toast({
        title: t.profile.deleteAccessCodeMissingTitle,
        description: t.profile.deleteAccessCodeMissingDescription,
        variant: 'destructive',
      });
      return;
    }

    setIsDeleting(true);
    try {
      await eventService.deleteMyAccount(password);
      toast({
        title: t.profile.deletedTitle,
        description: t.profile.deletedDescription,
      });
      closeDeleteDialog();
      logout();
      navigate('/');
    } catch (error: unknown) {
      console.error('Failed to delete account:', error);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.profile.deleteErrorTitle,
        description: axiosError.response?.data?.detail || t.profile.deleteErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  }, [closeDeleteDialog, deletePassword, logout, navigate, t, toast]);

  return {
    allTags,
    blockedOrganizers,
    city,
    cityOptions,
    closeDeleteDialog,
    deleteDialogOpen,
    deletePassword,
    faculty,
    facultyOptions,
    fullName,
    handleDeleteAccount,
    handleExport,
    handleLanguageChange,
    handleNotificationPreferenceChange,
    handleSave,
    handleStudyLevelChange,
    handleTagToggle,
    handleThemeChange,
    handleUnblockOrganizer,
    handleUnhideTag,
    handleUniversityChange,
    hiddenTags,
    isDeleting,
    isExporting,
    isLoading,
    isSaving,
    isSavingLanguage,
    isSavingNotifications,
    isSavingTheme,
    isStudent,
    languagePreference,
    musicTags,
    notificationPrefs,
    otherTags,
    profile,
    selectedTagIds,
    selectedUniversity,
    setCity,
    setDeleteDialogOpen,
    setDeletePassword,
    setFaculty,
    setFullName,
    setStudyYear,
    studyLevel,
    studyYear,
    studyYearOptions,
    t,
    themePreference,
    university,
    universityCatalog,
  };
}
