import { useState } from 'react';
import type {
  NotificationPreferences,
  PersonalizationSettings,
  StudyLevel,
  StudentProfile,
  Tag,
  UniversityCatalogItem,
} from '@/types';

/** Own the raw editable state that backs the student profile screen. */
/**
 * React hook: student profile state.
 */
export function useStudentProfileState() {
  const [isLoading, setIsLoading] = useState(true);
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
    faculty,
    fullName,
    isLoading,
    notificationPrefs,
    personalization,
    profile,
    selectedTagIds,
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
    studyLevel,
    studyYear,
    university,
    universityCatalog,
  };
}
