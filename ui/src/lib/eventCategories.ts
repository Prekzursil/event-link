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

