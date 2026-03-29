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

type InterestTagGroups = Readonly<{
  musicTags: Tag[];
  otherTags: Tag[];
}>;

type DerivedCollections = Readonly<{
  blockedOrganizers: PersonalizationSettings['blocked_organizers'];
  cityOptions: string[];
  currentNotificationPreferences: NotificationPreferences | null;
  currentPersonalization: PersonalizationSettings | null;
  facultyOptions: string[];
  hiddenTags: PersonalizationSettings['hidden_tags'];
  selectedUniversity: UniversityCatalogItem | null;
  studyYearOptions: number[];
}>;

/** Partition all profile tags into music interests and the remaining tags. */
function groupInterestTags(allTags: Tag[]): InterestTagGroups {
  return {
    musicTags: allTags.filter((tag) => MUSIC_INTEREST_NAMES.has(tag.name)),
    otherTags: allTags.filter((tag) => !MUSIC_INTEREST_NAMES.has(tag.name)),
  };
}

/** Compute the memoized option collections derived from the current profile state. */
function buildDerivedCollections({
  language,
  notificationPrefs,
  personalization,
  studyLevel,
  university,
  universityCatalog,
}: Omit<DerivedStateArgs, 'allTags'>): DerivedCollections {
  const selectedUniversity = findSelectedUniversity(university, universityCatalog);
  const currentPersonalization = personalization ?? null;

  return {
    blockedOrganizers: currentPersonalization?.blocked_organizers ?? [],
    cityOptions: buildCityOptions(universityCatalog, language),
    currentNotificationPreferences: notificationPrefs ?? null,
    currentPersonalization,
    facultyOptions: selectedUniversity?.faculties ?? [],
    hiddenTags: currentPersonalization?.hidden_tags ?? [],
    selectedUniversity,
    studyYearOptions: buildStudyYearOptions(studyLevel, MAX_YEARS_BY_LEVEL),
  };
}

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
  const { musicTags, otherTags } = useMemo(() => groupInterestTags(allTags), [allTags]);
  const {
    blockedOrganizers,
    cityOptions,
    currentNotificationPreferences,
    currentPersonalization,
    facultyOptions,
    hiddenTags,
    selectedUniversity,
    studyYearOptions,
  } = useMemo(() => buildDerivedCollections({
    language,
    notificationPrefs,
    personalization,
    studyLevel,
    university,
    universityCatalog,
  }), [
    language,
    notificationPrefs,
    personalization,
    studyLevel,
    university,
    universityCatalog,
  ]);

  return {
    blockedOrganizers,
    cityOptions,
    currentNotificationPreferences,
    currentPersonalization,
    facultyOptions,
    hiddenTags,
    musicTags,
    otherTags,
    selectedUniversity,
    studyYearOptions,
  };
}
