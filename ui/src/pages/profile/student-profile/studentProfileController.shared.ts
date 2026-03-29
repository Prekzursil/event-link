import { type Dispatch, type SetStateAction } from 'react';
import eventService from '@/services/event.service';
import type {
  NotificationPreferences,
  PersonalizationSettings,
  StudyLevel,
  StudentProfile,
  Tag,
  UniversityCatalogItem,
} from '@/types';

export type ToastFn = ReturnType<typeof import('@/hooks/use-toast').useToast>['toast'];
export type TranslationStrings = ReturnType<typeof import('@/contexts/LanguageContext').useI18n>['t'];
export type RefreshUser = ReturnType<typeof import('@/contexts/AuthContext').useAuth>['refreshUser'];
export type Logout = ReturnType<typeof import('@/contexts/AuthContext').useAuth>['logout'];
export type SetThemePreference = ReturnType<typeof import('@/contexts/ThemeContext').useTheme>['setPreference'];
export type SetLanguagePreference = ReturnType<typeof import('@/contexts/LanguageContext').useI18n>['setPreference'];

export type ProfileSnapshotSetters = Readonly<{
  setCity: Dispatch<SetStateAction<string>>;
  setFaculty: Dispatch<SetStateAction<string>>;
  setFullName: Dispatch<SetStateAction<string>>;
  setProfile: Dispatch<SetStateAction<StudentProfile | null>>;
  setSelectedTagIds: Dispatch<SetStateAction<number[]>>;
  setStudyLevel: Dispatch<SetStateAction<StudyLevel | ''>>;
  setStudyYear: Dispatch<SetStateAction<number | undefined>>;
  setUniversity: Dispatch<SetStateAction<string>>;
}>;

export const MUSIC_INTEREST_NAMES = new Set([
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

export const EMPTY_PERSONALIZATION: PersonalizationSettings = {
  hidden_tags: [],
  blocked_organizers: [],
};

export const EMPTY_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  email_digest_enabled: false,
  email_filling_fast_enabled: false,
};

/** Copy a nullable text field into a controlled string input setter. */
function applyTextSnapshot(setter: Dispatch<SetStateAction<string>>, value: string | null | undefined) {
  setter(value ?? '');
}

/** Copy an optional study-level value into a controlled select setter. */
function applyOptionalStudyLevelSnapshot(
  setter: Dispatch<SetStateAction<StudyLevel | ''>>,
  value: StudyLevel | null | undefined,
) {
  setter(value ?? '');
}

/** Copy an optional numeric study year into the corresponding controlled setter. */
function applyOptionalStudyYearSnapshot(
  setter: Dispatch<SetStateAction<number | undefined>>,
  value: number | null | undefined,
) {
  setter(typeof value === 'number' ? value : undefined);
}

/** Project the selected interest-tag identifiers from a loaded tag collection. */
function applyInterestTagSnapshot(setter: Dispatch<SetStateAction<number[]>>, tags: Tag[]) {
  setter(tags.map((tag) => tag.id));
}

/** Apply a loaded profile payload to the editable student-profile form state. */
export function applyProfileSnapshot(profileData: StudentProfile, setters: ProfileSnapshotSetters) {
  setters.setProfile(profileData);
  applyTextSnapshot(setters.setFullName, profileData.full_name);
  applyTextSnapshot(setters.setCity, profileData.city);
  applyTextSnapshot(setters.setUniversity, profileData.university);
  applyTextSnapshot(setters.setFaculty, profileData.faculty);
  applyOptionalStudyLevelSnapshot(setters.setStudyLevel, profileData.study_level);
  applyOptionalStudyYearSnapshot(setters.setStudyYear, profileData.study_year);
  applyInterestTagSnapshot(setters.setSelectedTagIds, profileData.interest_tags);
}

/** Match the free-text university selection against the loaded catalog. */
export function findSelectedUniversity(university: string, universityCatalog: UniversityCatalogItem[]) {
  const normalized = university.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return universityCatalog.find((item) => item.name.toLowerCase() === normalized) ?? null;
}

/** Build a sorted list of unique city options from the university catalog. */
export function buildCityOptions(universityCatalog: UniversityCatalogItem[], language: string) {
  const options = new Set<string>();
  for (const item of universityCatalog) {
    if (item.city) {
      options.add(item.city);
    }
  }
  return Array.from(options).sort((left, right) => left.localeCompare(right, language));
}

/** Expand the active study level into the available academic-year options. */
export function buildStudyYearOptions(studyLevel: StudyLevel | '', maxYearsByLevel: Record<StudyLevel, number>) {
  if (!studyLevel) {
    return [];
  }
  const max = maxYearsByLevel[studyLevel];
  return Array.from({ length: max }, (_, idx) => idx + 1);
}

/** Normalize the editable profile form state into an update payload. */
export function buildProfileUpdatePayload({
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

/** Load student-only personalization state while tolerating optional endpoint failures. */
export async function loadOptionalStudentState(isStudent: boolean) {
  if (!isStudent) {
    return {
      notificationPreferences: null,
      personalization: null,
    };
  }

  const [notificationPreferences, personalization] = await Promise.all([
    eventService.getNotificationPreferences().catch(() => EMPTY_NOTIFICATION_PREFERENCES),
    eventService.getPersonalizationSettings().catch(() => EMPTY_PERSONALIZATION),
  ]);

  return { notificationPreferences, personalization };
}

/** Load the university catalog without failing the whole profile bootstrap flow. */
export async function loadUniversityCatalog() {
  try {
    return await eventService.getUniversityCatalog();
  } catch {
    return [];
  }
}

/** Download an exported student-data blob through a temporary anchor element. */
export function triggerDataExport(blob: Blob) {
  const url = globalThis.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `eventlink-export-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  globalThis.URL.revokeObjectURL(url);
}
