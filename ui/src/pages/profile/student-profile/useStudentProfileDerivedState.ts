import { useMemo } from 'react';
import type {
  NotificationPreferences,
  PersonalizationSettings,
  StudyLevel,
  Tag,
  UniversityCatalogItem,
} from '@/types';
import {
  buildCityOptions,
  buildStudyYearOptions,
  findSelectedUniversity,
  MUSIC_INTEREST_NAMES,
} from './studentProfileController.shared';
import { MAX_YEARS_BY_LEVEL } from './shared';

type DerivedStateArgs = Readonly<{
  allTags: Tag[];
  language: string;
  notificationPrefs: NotificationPreferences | null;
  personalization: PersonalizationSettings | null;
  studyLevel: StudyLevel | '';
  university: string;
  universityCatalog: UniversityCatalogItem[];
}>;

/** Compute memoized option lists and filtered profile metadata from raw state. */
export function useStudentProfileDerivedState({
  allTags,
  language,
  notificationPrefs,
  personalization,
  studyLevel,
  university,
  universityCatalog,
}: DerivedStateArgs) {
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
  const hiddenTags = personalization?.hidden_tags ?? [];
  const blockedOrganizers = personalization?.blocked_organizers ?? [];
  const cityOptions = useMemo(
    () => buildCityOptions(universityCatalog, language),
    [language, universityCatalog],
  );
  const studyYearOptions = useMemo(
    () => buildStudyYearOptions(studyLevel, MAX_YEARS_BY_LEVEL),
    [studyLevel],
  );

  return {
    blockedOrganizers,
    cityOptions,
    currentNotificationPreferences: notificationPrefs ?? null,
    currentPersonalization: personalization ?? null,
    facultyOptions,
    hiddenTags,
    musicTags,
    otherTags,
    selectedUniversity,
    studyYearOptions,
  };
}
