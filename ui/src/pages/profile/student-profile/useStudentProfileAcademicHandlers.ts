import { useCallback } from 'react';
import type { StudyLevel, UniversityCatalogItem } from '@/types';
import { MAX_YEARS_BY_LEVEL } from './shared';
import { findSelectedUniversity, type ProfileSnapshotSetters } from './studentProfileController.shared';

type AcademicHandlersArgs = ProfileSnapshotSetters & Readonly<{
  studyYear: number | undefined;
  university: string;
  universityCatalog: UniversityCatalogItem[];
}>;

/** Derive field-level profile handlers for academic and university inputs. */
export function useStudentProfileAcademicHandlers(args: AcademicHandlersArgs) {
  const {
    setCity,
    setFaculty,
    setSelectedTagIds,
    setStudyLevel,
    setStudyYear,
    setUniversity,
    studyYear,
    university,
    universityCatalog,
  } = args;

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
      setStudyYear(() => undefined);
    }
  }, [setStudyLevel, setStudyYear, studyYear]);

  return {
    handleStudyLevelChange,
    handleTagToggle,
    handleUniversityChange,
  };
}
