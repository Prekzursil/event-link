import { useCallback, useEffect, type Dispatch, type SetStateAction } from 'react';
import eventService from '@/services/event.service';
import type {
  NotificationPreferences,
  PersonalizationSettings,
  Tag,
  UniversityCatalogItem,
} from '@/types';
import {
  applyProfileSnapshot,
  loadOptionalStudentState,
  loadUniversityCatalog,
  type ProfileSnapshotSetters,
  type ToastFn,
  type TranslationStrings,
} from './studentProfileController.shared';

type DataLoaderArgs = ProfileSnapshotSetters & Readonly<{
  isStudent: boolean;
  setAllTags: Dispatch<SetStateAction<Tag[]>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setNotificationPrefs: Dispatch<SetStateAction<NotificationPreferences | null>>;
  setPersonalization: Dispatch<SetStateAction<PersonalizationSettings | null>>;
  setUniversityCatalog: Dispatch<SetStateAction<UniversityCatalogItem[]>>;
  t: TranslationStrings;
  toast: ToastFn;
}>;

/** Load the editable profile form state, tags, and optional student preferences. */
/**
 * React hook: student profile data loader.
 */
export function useStudentProfileDataLoader({
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
}: DataLoaderArgs) {
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

      const { notificationPreferences, personalization } = await loadOptionalStudentState(isStudent);
      setNotificationPrefs(notificationPreferences);
      setPersonalization(personalization);
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
    loadData();
  }, [loadData]);
}
