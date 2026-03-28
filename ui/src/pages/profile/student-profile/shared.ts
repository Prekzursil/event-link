import type { useI18n } from '@/contexts/LanguageContext';
import type { StudyLevel } from '@/types';

export const MAX_YEARS_BY_LEVEL: Record<StudyLevel, number> = {
  bachelor: 4,
  master: 2,
  phd: 4,
  medicine: 6,
};

export type ProfileTexts = ReturnType<typeof useI18n>['t'];
