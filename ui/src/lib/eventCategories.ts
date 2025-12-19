export const EVENT_CATEGORIES = [
  'Technical',
  'Academic',
  'Workshop',
  'Seminar',
  'Presentation',
  'Conference',
  'Hackathon',
  'Networking',
  'Career Fair',
  'Music',
  'Cultural',
  'Sports',
  'Social',
  'Volunteering',
  'Party',
  'Festival',
] as const;

export type EventCategory = (typeof EVENT_CATEGORIES)[number];

export const EVENT_CATEGORY_LABELS: Record<'ro' | 'en', Record<EventCategory, string>> = {
  ro: {
    Technical: 'Tehnic',
    Academic: 'Academic',
    Workshop: 'Workshop',
    Seminar: 'Seminar',
    Presentation: 'Prezentare',
    Conference: 'Conferință',
    Hackathon: 'Hackathon',
    Networking: 'Networking',
    'Career Fair': 'Târg de cariere',
    Music: 'Muzică',
    Cultural: 'Cultural',
    Sports: 'Sport',
    Social: 'Social',
    Volunteering: 'Voluntariat',
    Party: 'Petrecere',
    Festival: 'Festival',
  },
  en: {
    Technical: 'Technical',
    Academic: 'Academic',
    Workshop: 'Workshop',
    Seminar: 'Seminar',
    Presentation: 'Presentation',
    Conference: 'Conference',
    Hackathon: 'Hackathon',
    Networking: 'Networking',
    'Career Fair': 'Career Fair',
    Music: 'Music',
    Cultural: 'Cultural',
    Sports: 'Sports',
    Social: 'Social',
    Volunteering: 'Volunteering',
    Party: 'Party',
    Festival: 'Festival',
  },
};

export function getEventCategoryLabel(category: string | undefined | null, language: 'ro' | 'en'): string | undefined {
  if (!category) return undefined;
  const cat = category as EventCategory;
  if ((EVENT_CATEGORIES as readonly string[]).includes(cat)) {
    return EVENT_CATEGORY_LABELS[language][cat];
  }
  return category;
}
