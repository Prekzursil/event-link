import { useCallback, useState } from 'react';
import eventService from '@/services/event.service';
import type { StudyLevel } from '@/types';
import {
  applyProfileSnapshot,
  buildProfileUpdatePayload,
  type ProfileSnapshotSetters,
  type ToastFn,
  type TranslationStrings,
} from './studentProfileController.shared';

type SaveHandlerArgs = ProfileSnapshotSetters & Readonly<{
  city: string;
  faculty: string;
  fullName: string;
  selectedTagIds: number[];
  studyLevel: StudyLevel | '';
  studyYear: number | undefined;
  t: TranslationStrings;
  toast: ToastFn;
  university: string;
}>;

/** Persist the edited student profile and project the saved snapshot back into form state. */
async function saveStudentProfileUpdates(args: SaveHandlerArgs) {
  const {
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
  } = args;

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
  toast({ title: t.profile.saveSuccessTitle, description: t.profile.saveSuccessDescription });
}

/** Persist the editable student-profile form and expose save progress state. */
export function useStudentProfileSaveHandler({
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
}: SaveHandlerArgs) {
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      await saveStudentProfileUpdates({
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
      });
    } catch {
      toast({ title: t.profile.saveErrorTitle, description: t.profile.saveErrorDescription, variant: 'destructive' });
    } finally {
      setIsSaving(false);
    }
  }, [city, faculty, fullName, selectedTagIds, setCity, setFaculty, setFullName, setProfile, setSelectedTagIds, setStudyLevel, setStudyYear, setUniversity, studyLevel, studyYear, t, toast, university]);

  return { handleSave, isSaving };
}
