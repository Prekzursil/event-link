/* eslint-disable react-refresh/only-export-components */

import React from 'react';
import { cleanup } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

import { defineMutableValue, setEnglishPreference } from './page-test-helpers';

const highImpactPageFixtures = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  recordInteractionsSpy: vi.fn(),
  eventServiceMock: {
    getEvents: vi.fn(),
    getFavorites: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    getStudentProfile: vi.fn(),
    getAllTags: vi.fn(),
    getPersonalizationSettings: vi.fn(),
    getNotificationPreferences: vi.fn(),
    getUniversityCatalog: vi.fn(),
    updateStudentProfile: vi.fn(),
    updateNotificationPreferences: vi.fn(),
    unhideTag: vi.fn(),
    unblockOrganizer: vi.fn(),
    exportMyData: vi.fn(),
    deleteMyAccount: vi.fn(),
    getOrganizerEvents: vi.fn(),
    bulkUpdateEventStatus: vi.fn(),
    bulkUpdateEventTags: vi.fn(),
    deleteEvent: vi.fn(),
  },
  authServiceMock: {
    updateThemePreference: vi.fn(),
    updateLanguagePreference: vi.fn(),
  },
  authState: {
    isAuthenticated: true,
    isOrganizer: true,
    isAdmin: false,
    isLoading: false,
    user: { id: 11, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  themeState: {
    preference: 'system',
    setPreference: vi.fn(),
  },
  mediaAddListenerSpy: vi.fn(),
  mediaRemoveListenerSpy: vi.fn(),
}));

const {
  toastSpy,
  navigateSpy,
  recordInteractionsSpy,
  eventServiceMock,
  authServiceMock,
  authState,
  themeState,
  mediaAddListenerSpy,
  mediaRemoveListenerSpy,
} = highImpactPageFixtures;

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/auth.service', () => ({ default: authServiceMock }));
vi.mock('@/services/analytics.service', () => ({ recordInteractions: recordInteractionsSpy }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));
vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => themeState }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);
vi.mock('@/components/ui/checkbox', () =>
  import('./mock-component-modules').then((module) => module.createCheckboxMockModule()),
);
vi.mock('@/components/ui/calendar', () =>
  import('./mock-component-modules').then((module) => module.createCalendarMockModule()),
);
vi.mock('@/components/events/EventCard', () => ({
  EventCard: ({
    event,
    onFavoriteToggle,
    onEventClick,
    isFavorite,
  }: {
    event: { id: number; title: string };
    onFavoriteToggle?: (eventId: number, shouldFavorite: boolean) => void;
    onEventClick?: (eventId: number) => void;
    isFavorite?: boolean;
  }) => (
    <div data-testid={`event-${event.id}`}>
      <span>{event.title}</span>
      <button type="button" onClick={() => onFavoriteToggle?.(event.id, !isFavorite)}>
        toggle-favorite-{event.id}
      </button>
      <button type="button" onClick={() => onEventClick?.(event.id)}>
        open-event-{event.id}
      </button>
    </div>
  ),
}));

export { EventsPage } from '@/pages/events/EventsPage';
export { OrganizerDashboardPage } from '@/pages/organizer/OrganizerDashboardPage';
export { StudentProfilePage } from '@/pages/profile/StudentProfilePage';

export function getHighImpactPageFixtures() {
  return highImpactPageFixtures;
}

const {
  makeEvent,
  makeNotificationPreferences,
  makePersonalizationSettings,
  makeStudentProfile,
  makeUniversityCatalog,
  makeUpdatedStudentProfile,
} = await import('./page-test-data');

export { makeEvent };

function seedBrowserGlobals() {
  defineMutableValue(
    globalThis,
    'matchMedia',
    vi.fn().mockImplementation(() => ({
      matches: false,
      media: '(min-width: 640px)',
      addListener: mediaAddListenerSpy,
      removeListener: mediaRemoveListenerSpy,
    })),
  );
  defineMutableValue(globalThis, 'confirm', vi.fn().mockReturnValue(true));
  defineMutableValue(globalThis, 'open', vi.fn());
  defineMutableValue(URL, 'createObjectURL', vi.fn().mockReturnValue('blob://data'));
}

function seedAuthDefaults() {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.user = { id: 11, role: 'student', email: 'student@test.local' };
  authState.refreshUser.mockResolvedValue(undefined);
  authState.logout.mockResolvedValue(undefined);
}

function seedEventListDefaults() {
  eventServiceMock.getEvents.mockResolvedValue({
    items: [makeEvent(1)],
    total: 1,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  eventServiceMock.getFavorites.mockResolvedValue({ items: [makeEvent(1)] });
  eventServiceMock.addToFavorites.mockResolvedValue(undefined);
  eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
}

function seedProfileDefaults() {
  eventServiceMock.getStudentProfile.mockResolvedValue(makeStudentProfile(11, { study_year: 4 }));
  eventServiceMock.getAllTags.mockResolvedValue([
    { id: 1, name: 'Muzică' },
    { id: 2, name: 'Tech' },
  ]);
  eventServiceMock.getPersonalizationSettings.mockResolvedValue(
    makePersonalizationSettings({
      hidden_tags: [{ id: 5, name: 'Hidden' }],
      blocked_organizers: [
        { id: 77, org_name: 'Muted Org', full_name: 'Muted Org', email: 'muted@test.local' },
      ],
    }),
  );
  eventServiceMock.getNotificationPreferences.mockResolvedValue(makeNotificationPreferences());
  eventServiceMock.getUniversityCatalog.mockResolvedValue(makeUniversityCatalog());
  eventServiceMock.updateStudentProfile.mockResolvedValue(
    makeUpdatedStudentProfile(11, {
      faculty: 'Informatica',
      study_level: 'master',
      study_year: 1,
    }),
  );
  eventServiceMock.updateNotificationPreferences.mockResolvedValue(
    makeNotificationPreferences({
      email_digest_enabled: false,
      email_filling_fast_enabled: true,
    }),
  );
  eventServiceMock.unhideTag.mockResolvedValue(undefined);
  eventServiceMock.unblockOrganizer.mockResolvedValue(undefined);
  eventServiceMock.exportMyData.mockResolvedValue(
    new Blob(['{"ok":true}'], { type: 'application/json' }),
  );
  eventServiceMock.deleteMyAccount.mockResolvedValue(undefined);
}

function seedOrganizerDefaults() {
  eventServiceMock.getOrganizerEvents.mockResolvedValue([makeEvent(3)]);
  eventServiceMock.bulkUpdateEventStatus.mockResolvedValue({ updated: 1 });
  eventServiceMock.bulkUpdateEventTags.mockResolvedValue({ updated: 1 });
  eventServiceMock.deleteEvent.mockResolvedValue(undefined);
}

function seedAuthServiceDefaults() {
  authServiceMock.updateThemePreference.mockResolvedValue(undefined);
  authServiceMock.updateLanguagePreference.mockResolvedValue(undefined);
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();
  seedBrowserGlobals();
  seedAuthDefaults();
  seedEventListDefaults();
  seedProfileDefaults();
  seedOrganizerDefaults();
  seedAuthServiceDefaults();
});
