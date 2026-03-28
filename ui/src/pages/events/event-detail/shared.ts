import type { useI18n } from '@/contexts/LanguageContext';

export type EventDetailTexts = ReturnType<typeof useI18n>['t'];

export const EVENT_DETAIL_FALLBACK_COVER_URL =
  'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=1200&h=600&fit=crop';
