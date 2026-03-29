import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
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
  StudentProfile,
  Tag,
  ThemePreference,
  UniversityCatalogItem,
} from '@/types';
import { MAX_YEARS_BY_LEVEL } from './shared';

type ToastFn = ReturnType<typeof useToast>['toast'];
type TranslationStrings = ReturnType<typeof useI18n>['t'];
type RefreshUser = ReturnType<typeof useAuth>['refreshUser'];
type Logout = ReturnType<typeof useAuth>['logout'];
type SetThemePreference = ReturnType<typeof useTheme>['setPreference'];
type SetLanguagePreference = ReturnType<typeof useI18n>['setPreference'];
type OptionalStudentState = {
  personalization: PersonalizationSettings | null;
  notificationPreferences: NotificationPreferences | null;
};
type ProfileSnapshotSetters = {
  setCity: Dispatch<SetStateAction<string>>;
  setFaculty: Dispatch<SetStateAction<string>>;
  setFullName: Dispatch<SetStateAction<string>>;
  setProfile: Dispatch<SetStateAction<StudentProfile | null>>;
  setSelectedTagIds: Dispatch<SetStateAction<number[]>>;
  setStudyLevel: Dispatch<SetStateAction<StudyLevel | ''>>;
  setStudyYear: Dispatch<SetStateAction<number | undefined>>;
  setUniversity: Dispatch<SetStateAction<string>>;
};
type ProfileDataLoaderArgs = ProfileSnapshotSetters & {
  isStudent: boolean;
  setAllTags: Dispatch<SetStateAction<Tag[]>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setNotificationPrefs: Dispatch<SetStateAction<NotificationPreferences | null>>;
  setPersonalization: Dispatch<SetStateAction<PersonalizationSettings | null>>;
  setUniversityCatalog: Dispatch<SetStateAction<UniversityCatalogItem[]>>;
  t: TranslationStrings;
  toast: ToastFn;
};
type ProfileFormHandlerArgs = ProfileSnapshotSetters & {
  city: string;
  faculty: string;
  fullName: string;
  selectedTagIds: number[];
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  toast: ToastFn;
  t: TranslationStrings;
  university: string;
  universityCatalog: UniversityCatalogItem[];
};
type PreferenceHandlerArgs = {
  currentNotificationPreferences: NotificationPreferences | null;
  currentPersonalization: PersonalizationSettings | null;
  languagePreference: LanguagePreference;
  refreshUser: RefreshUser;
  setLanguagePreference: SetLanguagePreference;
  setNotificationPrefs: Dispatch<SetStateAction<NotificationPreferences | null>>;
  setPersonalization: Dispatch<SetStateAction<PersonalizationSettings | null>>;
  setThemePreference: SetThemePreference;
  t: TranslationStrings;
  themePreference: ThemePreference;
  toast: ToastFn;
};
type AccountHandlerArgs = {
  closeDeleteDialog: () => void;
  deletePassword: string;
  logout: Logout;
  navigate: ReturnType<typeof useNavigate>;
  t: TranslationStrings;
  toast: ToastFn;
};
type StudentProfileControllerState = {
  allTags: Tag[];
  city: string;
  deleteDialogOpen: boolean;
  deletePassword: string;
  faculty: string;
  fullName: string;
  isLoading: boolean;
  notificationPrefs: NotificationPreferences | null;
  personalization: PersonalizationSettings | null;
  profile: StudentProfile | null;
  selectedTagIds: number[];
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  university: string;
  universityCatalog: UniversityCatalogItem[];
  setAllTags: Dispatch<SetStateAction<Tag[]>>;
  setCity: Dispatch<SetStateAction<string>>;
  setDeleteDialogOpen: Dispatch<SetStateAction<boolean>>;
  setDeletePassword: Dispatch<SetStateAction<string>>;
  setFaculty: Dispatch<SetStateAction<string>>;
  setFullName: Dispatch<SetStateAction<string>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setNotificationPrefs: Dispatch<SetStateAction<NotificationPreferences | null>>;
  setPersonalization: Dispatch<SetStateAction<PersonalizationSettings | null>>;
  setProfile: Dispatch<SetStateAction<StudentProfile | null>>;
  setSelectedTagIds: Dispatch<SetStateAction<number[]>>;
  setStudyLevel: Dispatch<SetStateAction<StudyLevel | ''>>;
  setStudyYear: Dispatch<SetStateAction<number | undefined>>;
  setUniversity: Dispatch<SetStateAction<string>>;
  setUniversityCatalog: Dispatch<SetStateAction<UniversityCatalogItem[]>>;
};
type StudentProfileControllerDerivedData = {
  blockedOrganizers: PersonalizationSettings['blocked_organizers'];
  cityOptions: string[];
  currentNotificationPreferences: NotificationPreferences | null;
  currentPersonalization: PersonalizationSettings | null;
  facultyOptions: string[];
  hiddenTags: PersonalizationSettings['hidden_tags'];
  musicTags: Tag[];
  otherTags: Tag[];
  selectedUniversity: UniversityCatalogItem | null;
  studyYearOptions: number[];
};

const MUSIC_INTEREST_NAMES = new Set([
  'Muzică',
  'Rock',
  'Pop',
  'Hip-Hop',
  'EDM',
  'Jazz',
  'Clasică',
  'Folk',
  'Metal',
]);

const EMPTY_PERSONALIZATION: PersonalizationSettings = {
  hidden_tags: [],
  blocked_organizers: [],
};

const EMPTY_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  email_digest_enabled: false,
  email_filling_fast_enabled: false,
};

function applyProfileSnapshot(profileData: StudentProfile, setters: ProfileSnapshotSetters) {
  setters.setProfile(profileData);
  setters.setFullName(profileData.full_name ?? '');
  setters.setCity(profileData.city ?? '');
  setters.setUniversity(profileData.university ?? '');
  setters.setFaculty(profileData.faculty ?? '');
  setters.setStudyLevel(profileData.study_level ?? '');
  setters.setStudyYear(profileData.study_year ?? undefined);
  setters.setSelectedTagIds(profileData.interest_tags.map((tag) => tag.id));
}

function findSelectedUniversity(
  university: string,
  universityCatalog: UniversityCatalogItem[],
) {
  const normalized = university.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return universityCatalog.find((item) => item.name.toLowerCase() === normalized) ?? null;
}

function buildCityOptions(universityCatalog: UniversityCatalogItem[], language: string) {
  const options = new Set<string>();
  for (const item of universityCatalog) {
    if (item.city) {
      options.add(item.city);
    }
  }
  return Array.from(options).sort((left, right) => left.localeCompare(right, language));
}

function buildStudyYearOptions(studyLevel: StudyLevel | '') {
  if (!studyLevel) {
    return [];
  }
  const max = MAX_YEARS_BY_LEVEL[studyLevel];
  return Array.from({ length: max }, (_, idx) => idx + 1);
}

function buildProfileUpdatePayload({
  city,
  faculty,
  fullName,
  selectedTagIds,
  studyLevel,
  studyYear,
  university,
}: {
  city: string;
  faculty: string;
  fullName: string;
  selectedTagIds: number[];
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  university: string;
}) {
  return {
    full_name: fullName.trim() ? fullName.trim() : undefined,
    city: city.trim(),
    university: university.trim(),
    faculty: faculty.trim(),
    study_level: studyLevel || undefined,
    study_year: typeof studyYear === 'number' ? studyYear : undefined,
    interest_tag_ids: selectedTagIds,
  };
}

async function loadOptionalStudentState(isStudent: boolean): Promise<OptionalStudentState> {
  if (!isStudent) {
    return {
      personalization: null,
      notificationPreferences: null,
    };
  }

  const [personalization, notificationPreferences] = await Promise.all([
    eventService.getPersonalizationSettings().catch(() => EMPTY_PERSONALIZATION),
    eventService.getNotificationPreferences().catch(() => EMPTY_NOTIFICATION_PREFERENCES),
  ]);

  return { personalization, notificationPreferences };
}

async function loadUniversityCatalog() {
  try {
    return await eventService.getUniversityCatalog();
  } catch {
    return [];
  }
}

function triggerDataExport(blob: Blob) {
  const url = globalThis.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `eventlink-export-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  globalThis.URL.revokeObjectURL(url);
}

function useStudentProfileState(): StudentProfileControllerState {
  const [isLoading, setIsLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
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

  return {
    allTags,
    city,
    deleteDialogOpen,
    deletePassword,
    faculty,
    fullName,
    isLoading,
    notificationPrefs,
    personalization,
    profile,
    selectedTagIds,
    setAllTags,
    setCity,
    setDeleteDialogOpen,
    setDeletePassword,
    setFaculty,
    setFullName,
    setIsLoading,
    setNotificationPrefs,
    setPersonalization,
    setProfile,
    setSelectedTagIds,
    setStudyLevel,
    setStudyYear,
    setUniversity,
    setUniversityCatalog,
    studyLevel,
    studyYear,
    university,
    universityCatalog,
  };
}

function useStudentProfileDerivedValues({
  allTags,
  language,
  notificationPrefs,
  personalization,
  studyLevel,
  university,
  universityCatalog,
}: {
  allTags: Tag[];
  language: string;
  notificationPrefs: NotificationPreferences | null;
  personalization: PersonalizationSettings | null;
  studyLevel: StudyLevel | '';
  university: string;
  universityCatalog: UniversityCatalogItem[];
}): StudentProfileControllerDerivedData {
  const musicTags = useMemo(
    () => allTags.filter((tag) => MUSIC_INTEREST_NAMES.has(tag.name)),
    [allTags],
  );
  const otherTags = useMemo(
    () => allTags.filter((tag) => !MUSIC_INTEREST_NAMES.has(tag.name)),
    [allTags],
  );
  const selectedUniversity = useMemo(
    () => findSelectedUniversity(university, universityCatalog),
    [university, universityCatalog],
  );
  const facultyOptions = useMemo(() => selectedUniversity?.faculties ?? [], [selectedUniversity]);
  const cityOptions = useMemo(
    () => buildCityOptions(universityCatalog, language),
    [language, universityCatalog],
  );
  const studyYearOptions = useMemo(() => buildStudyYearOptions(studyLevel), [studyLevel]);

  return {
    blockedOrganizers: personalization?.blocked_organizers ?? [],
    cityOptions,
    currentNotificationPreferences: notificationPrefs ?? null,
    currentPersonalization: personalization ?? null,
    facultyOptions,
    hiddenTags: personalization?.hidden_tags ?? [],
    musicTags,
    otherTags,
    selectedUniversity,
    studyYearOptions,
  };
}

function useStudentProfileDataLoader({
  isStudent,
  setAllTags,
  setCity,
  setFaculty,
  setFullName,
  setIsLoading,
  setNotificationPrefs,
  setPersonalization,
  setProfile,
  setSelectedTagIds,
  setStudyLevel,
  setStudyYear,
  setUniversity,
  setUniversityCatalog,
  t,
  toast,
}: ProfileDataLoaderArgs) {
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [profileData, tagsData] = await Promise.all([
        eventService.getStudentProfile(),
        eventService.getAllTags(),
      ]);
      applyProfileSnapshot(profileData, {
        setCity,
        setFaculty,
        setFullName,
        setProfile,
        setSelectedTagIds,
        setStudyLevel,
        setStudyYear,
        setUniversity,
      });
      setAllTags(tagsData);

      const { personalization, notificationPreferences } = await loadOptionalStudentState(isStudent);
      setPersonalization(personalization);
      setNotificationPrefs(notificationPreferences);
      setUniversityCatalog(await loadUniversityCatalog());
    } catch {
      toast({
        title: t.profile.loadErrorTitle,
        description: t.profile.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [
    isStudent,
    setAllTags,
    setCity,
    setFaculty,
    setFullName,
    setIsLoading,
    setNotificationPrefs,
    setPersonalization,
    setProfile,
    setSelectedTagIds,
    setStudyLevel,
    setStudyYear,
    setUniversity,
    setUniversityCatalog,
    t,
    toast,
  ]);

  useEffect(() => {
    void loadData();
  }, [loadData]);
}

function useStudentProfileFormHandlers({
  city,
  faculty,
  fullName,
  selectedTagIds,
  setCity,
  setFaculty,
  setFullName,
  setProfile,
  setSelectedTagIds,
  setStudyLevel,
  setStudyYear,
  setUniversity,
  studyLevel,
  studyYear,
  t,
  toast,
  university,
  universityCatalog,
}: ProfileFormHandlerArgs) {
  const [isSaving, setIsSaving] = useState(false);

  const handleTagToggle = useCallback((tagId: number) => {
    setSelectedTagIds((previous) => (
      previous.includes(tagId)
        ? previous.filter((id) => id !== tagId)
        : [...previous, tagId]
    ));
  }, [setSelectedTagIds]);

  const handleUniversityChange = useCallback((nextUniversity: string) => {
    const match = findSelectedUniversity(nextUniversity, universityCatalog);
    setUniversity(nextUniversity);
    if (nextUniversity !== university) {
      setFaculty('');
    }
    const matchedCity = typeof match?.city === 'string' && match.city.trim() ? match.city : '';
    if (matchedCity) {
      setCity((previousCity) => (previousCity.trim() ? previousCity : matchedCity));
    }
  }, [setCity, setFaculty, setUniversity, university, universityCatalog]);

  const handleStudyLevelChange = useCallback((value: string) => {
    const next = value as StudyLevel;
    setStudyLevel(next);
    const max = MAX_YEARS_BY_LEVEL[next];
    if (typeof studyYear === 'number' && (studyYear < 1 || studyYear > max)) {
      setStudyYear(undefined);
    }
  }, [setStudyLevel, setStudyYear, studyYear]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const updatedProfile = await eventService.updateStudentProfile(buildProfileUpdatePayload({
        city,
        faculty,
        fullName,
        selectedTagIds,
        studyLevel,
        studyYear,
        university,
      }));
      applyProfileSnapshot(updatedProfile, {
        setCity,
        setFaculty,
        setFullName,
        setProfile,
        setSelectedTagIds,
        setStudyLevel,
        setStudyYear,
        setUniversity,
      });
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
  }, [
    city,
    faculty,
    fullName,
    selectedTagIds,
    setCity,
    setFaculty,
    setFullName,
    setProfile,
    setSelectedTagIds,
    setStudyLevel,
    setStudyYear,
    setUniversity,
    studyLevel,
    studyYear,
    t,
    toast,
    university,
  ]);

  return {
    handleSave,
    handleStudyLevelChange,
    handleTagToggle,
    handleUniversityChange,
    isSaving,
  };
}

function useStudentProfilePreferenceHandlers({
  currentNotificationPreferences,
  currentPersonalization,
  languagePreference,
  refreshUser,
  setLanguagePreference,
  setNotificationPrefs,
  setPersonalization,
  setThemePreference,
  t,
  themePreference,
  toast,
}: PreferenceHandlerArgs) {
  const [isSavingTheme, setThemeSavingState] = useState(false);
  const [isSavingLanguage, setLanguageSavingState] = useState(false);
  const [isSavingNotifications, setNotificationSavingState] = useState(false);

  const handleThemeChange = useCallback(async (nextPreference: ThemePreference) => {
    const previous = themePreference;
    setThemePreference(nextPreference);
    setThemeSavingState(true);
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
      setThemeSavingState(false);
    }
  }, [refreshUser, setThemePreference, t, themePreference, toast]);

  const handleLanguageChange = useCallback(async (nextPreference: LanguagePreference) => {
    const previous = languagePreference;
    setLanguagePreference(nextPreference);
    setLanguageSavingState(true);
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
      setLanguageSavingState(false);
    }
  }, [languagePreference, refreshUser, setLanguagePreference, t, toast]);

  const handleNotificationPreferenceChange = useCallback(async (
    patch: Partial<NotificationPreferences>,
  ) => {
    if (!currentNotificationPreferences) {
      return;
    }

    const previous = currentNotificationPreferences;
    const next = { ...previous, ...patch };
    setNotificationPrefs(next);
    setNotificationSavingState(true);
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
      setNotificationSavingState(false);
    }
  }, [currentNotificationPreferences, setNotificationPrefs, t, toast]);

  const handleUnhideTag = useCallback(async (tagId: number) => {
    if (!currentPersonalization) {
      return;
    }

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
  }, [currentPersonalization, setPersonalization, t, toast]);

  const handleUnblockOrganizer = useCallback(async (organizerId: number) => {
    if (!currentPersonalization) {
      return;
    }

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
  }, [currentPersonalization, setPersonalization, t, toast]);

  return {
    handleLanguageChange,
    handleNotificationPreferenceChange,
    handleThemeChange,
    handleUnblockOrganizer,
    handleUnhideTag,
    isSavingLanguage,
    isSavingNotifications,
    isSavingTheme,
  };
}

function useStudentProfileAccountHandlers({
  closeDeleteDialog,
  deletePassword,
  logout,
  navigate,
  t,
  toast,
}: AccountHandlerArgs) {
  const [isDeleting, setDeletingState] = useState(false);
  const [isExporting, setExportingState] = useState(false);

  const handleExport = useCallback(async () => {
    setExportingState(true);
    try {
      const blob = await eventService.exportMyData();
      triggerDataExport(blob);
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
      setExportingState(false);
    }
  }, [t, toast]);

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

    setDeletingState(true);
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
      setDeletingState(false);
    }
  }, [closeDeleteDialog, deletePassword, logout, navigate, t, toast]);

  return {
    handleDeleteAccount,
    handleExport,
    isDeleting,
    isExporting,
  };
}

function useStudentProfileState() {
  const [isLoading, setIsLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpenState] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
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

  const setDeleteDialogOpen = useCallback((nextValue: SetStateAction<boolean>) => {
    setDeleteDialogOpenState((previous) => {
      const resolvedValue = typeof nextValue === 'function' ? nextValue(previous) : nextValue;
      if (!resolvedValue) {
        setDeletePassword('');
      }
      return resolvedValue;
    });
  }, []);

  return {
    allTags,
    city,
    deleteDialogOpen,
    deletePassword,
    faculty,
    fullName,
    isLoading,
    notificationPrefs,
    personalization,
    profile,
    selectedTagIds,
    setAllTags,
    setCity,
    setDeleteDialogOpen,
    setDeletePassword,
    setFaculty,
    setFullName,
    setIsLoading,
    setNotificationPrefs,
    setPersonalization,
    setProfile,
    setSelectedTagIds,
    setStudyLevel,
    setStudyYear,
    setUniversity,
    setUniversityCatalog,
    studyLevel,
    studyYear,
    university,
    universityCatalog,
  };
}

/** Coordinate student profile state, async mutations, and derived form options. */
export function useStudentProfileController() {
  const { toast } = useToast();
  const { user, logout, refreshUser } = useAuth();
  const { preference: themePreference, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, setPreference: setLanguagePreference, language, t } = useI18n();
  const navigate = useNavigate();
  const isStudent = user?.role === 'student';
  const state = useStudentProfileState();
  const derived = useStudentProfileDerivedValues({
    allTags: state.allTags,
    language,
    personalization: state.personalization,
    studyLevel: state.studyLevel,
    university: state.university,
    universityCatalog: state.universityCatalog,
  });
  const currentNotificationPreferences = state.notificationPrefs ?? null;
  const currentPersonalization = state.personalization ?? null;

  useStudentProfileDataLoader({
    isStudent,
    setAllTags: state.setAllTags,
    setCity: state.setCity,
    setFaculty: state.setFaculty,
    setFullName: state.setFullName,
    setIsLoading: state.setIsLoading,
    setNotificationPrefs: state.setNotificationPrefs,
    setPersonalization: state.setPersonalization,
    setProfile: state.setProfile,
    setSelectedTagIds: state.setSelectedTagIds,
    setStudyLevel: state.setStudyLevel,
    setStudyYear: state.setStudyYear,
    setUniversity: state.setUniversity,
    setUniversityCatalog: state.setUniversityCatalog,
    t,
    toast,
  });

  const formHandlers = useStudentProfileFormHandlers({
    city: state.city,
    faculty: state.faculty,
    fullName: state.fullName,
    selectedTagIds: state.selectedTagIds,
    setCity: state.setCity,
    setFaculty: state.setFaculty,
    setFullName: state.setFullName,
    setProfile: state.setProfile,
    setSelectedTagIds: state.setSelectedTagIds,
    setStudyLevel: state.setStudyLevel,
    setStudyYear: state.setStudyYear,
    setUniversity: state.setUniversity,
    studyLevel: state.studyLevel,
    studyYear: state.studyYear,
    t,
    toast,
    university: state.university,
    universityCatalog: state.universityCatalog,
  });

  const preferenceHandlers = useStudentProfilePreferenceHandlers({
    currentNotificationPreferences,
    currentPersonalization,
    languagePreference,
    refreshUser,
    setLanguagePreference,
    setNotificationPrefs: state.setNotificationPrefs,
    setPersonalization: state.setPersonalization,
    setThemePreference,
    t,
    themePreference,
    toast,
  });

  const closeDeleteDialog = useCallback(() => {
    state.setDeleteDialogOpen(false);
  }, [state]);

  const accountHandlers = useStudentProfileAccountHandlers({
    closeDeleteDialog,
    deletePassword: state.deletePassword,
    logout,
    navigate,
    t,
    toast,
  });

  return buildStudentProfileControllerResult({
    accountHandlers,
    closeDeleteDialog,
    derived,
    formHandlers,
    isStudent,
    languagePreference,
    preferenceHandlers,
    state,
    t,
    themePreference,
  });
}
