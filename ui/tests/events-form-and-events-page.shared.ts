import React from 'react';
import { cleanup } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

import { defineMutableValue, setEnglishPreference } from './page-test-helpers';

const eventPagesFixtures = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  recordInteractionsSpy: vi.fn(),
  eventServiceMock: {
    getEvents: vi.fn(),
    getFavorites: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    suggestEvent: vi.fn(),
    createEvent: vi.fn(),
    getEvent: vi.fn(),
    updateEvent: vi.fn(),
  },
  authState: {
    isAuthenticated: true,
    isOrganizer: true,
    isAdmin: false,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
}));

const {
  toastSpy,
  navigateSpy,
  recordInteractionsSpy,
  eventServiceMock,
  authState,
} = eventPagesFixtures;

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/analytics.service', () => ({ recordInteractions: recordInteractionsSpy }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));

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
  }) =>
    React.createElement(
      'div',
      { 'data-testid': `mock-event-card-${event.id}` },
      React.createElement('span', null, event.title),
      React.createElement(
        'button',
        { onClick: () => onFavoriteToggle?.(event.id, !isFavorite) },
        `favorite-${event.id}`,
      ),
      React.createElement(
        'button',
        { onClick: () => onEventClick?.(event.id) },
        `open-${event.id}`,
      ),
    ),
}));

export const { EventsPage } = await import('@/pages/events/EventsPage');
export const { EventFormPage } = await import('@/pages/organizer/EventFormPage');

/**
 * Test helper: get event pages fixtures.
 */
export function getEventPagesFixtures() {
  return eventPagesFixtures;
}

/**
 * Returns the form value or fails loudly when absent.
 */
export function requireForm(buttonName: RegExp, screen: typeof import('@testing-library/react').screen) {
  const form = screen.getByRole('button', { name: buttonName }).closest('form');
  if (!(form instanceof HTMLFormElement)) {
    throw new TypeError(`Expected a form for ${buttonName.toString()}`);
  }
  return form;
}

/**
 * Builds a event fixture.
 */
export function makeEvent(id: number, title = `Event ${id}`) {
  return {
    id,
    title,
    description: 'desc',
    category: 'Technical',
    start_time: new Date(Date.now() + 3_600_000).toISOString(),
    end_time: new Date(Date.now() + 7_200_000).toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 20,
    seats_taken: 2,
    tags: [{ id: 1, name: 'Tech' }],
    owner_id: 8,
    owner_name: 'Owner',
    recommendation_reason: 'Because you liked similar events',
    status: 'published',
  };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();

  defineMutableValue(
    globalThis,
    'matchMedia',
    vi.fn().mockImplementation(() => ({
      matches: true,
      media: '(min-width: 640px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  );

  authState.isAuthenticated = true;
  authState.user = { id: 1, role: 'student', email: 'student@test.local' };

  eventServiceMock.getEvents.mockImplementation((filters: { sort?: string; page_size?: number }) => {
    if (filters?.sort === 'recommended' && filters?.page_size === 4) {
      return Promise.resolve({
        items: [makeEvent(90, 'Recommended 90')],
        total: 1,
        page: 1,
        page_size: 4,
        total_pages: 1,
      });
    }
    return Promise.resolve({ items: [makeEvent(1)], total: 1, page: 1, page_size: 12, total_pages: 1 });
  });
  eventServiceMock.getFavorites.mockResolvedValue({ items: [makeEvent(90, 'Recommended 90')] });
  eventServiceMock.addToFavorites.mockResolvedValue();
  eventServiceMock.removeFromFavorites.mockResolvedValue();

  eventServiceMock.suggestEvent.mockResolvedValue({
    suggested_category: 'Technical',
    suggested_city: 'Cluj',
    suggested_tags: ['AI', 'Campus'],
    duplicates: [{ id: 200, title: 'Duplicate', start_time: new Date().toISOString(), city: 'Cluj', similarity: 0.95 }],
    moderation_score: 0.1,
    moderation_flags: ['potential_spam'],
    moderation_status: 'flagged',
  });
  eventServiceMock.createEvent.mockResolvedValue(makeEvent(77, 'Created event'));
  eventServiceMock.getEvent.mockResolvedValue({
    ...makeEvent(33, 'Editable event'),
    tags: [{ id: 3, name: 'Existing tag' }],
  });
  eventServiceMock.updateEvent.mockResolvedValue({ ...makeEvent(33, 'Editable event updated') });
});
