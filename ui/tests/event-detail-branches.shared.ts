import { cleanup } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

import { defineMutableValue, setEnglishPreference } from './page-test-helpers';

/** Creates the event-service mock used across event-detail tests. */
function createEventServiceMock() {
  return {
    getEvent: vi.fn(),
    registerForEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    cloneEvent: vi.fn(),
    hideTag: vi.fn(),
    blockOrganizer: vi.fn(),
  };
}

/** Creates the auth-state test double used across event-detail tests. */
function createAuthState() {
  return {
    isAuthenticated: true,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };
}

const eventDetailFixtures = vi.hoisted(() => ({
  eventServiceMock: createEventServiceMock(),
  recordInteractionsSpy: vi.fn(),
  authState: createAuthState(),
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
}));

const {
  eventServiceMock,
  recordInteractionsSpy,
  authState,
  toastSpy,
  navigateSpy,
} = eventDetailFixtures;

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

export const { EventDetailPage } = await import('@/pages/events/EventDetailPage');

/** Returns the shared event-detail fixtures for the current test module. */
export function getEventDetailFixtures() {
  return eventDetailFixtures;
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();

  defineMutableValue(globalThis, 'open', vi.fn());
  defineMutableValue(navigator, 'clipboard', {
    writeText: vi.fn().mockResolvedValue(undefined),
  });
  defineMutableValue(navigator, 'share', undefined);
  defineMutableValue(HTMLElement.prototype, 'scrollIntoView', vi.fn());

  authState.isAuthenticated = true;
  authState.user = { id: 1, role: 'student', email: 'student@test.local' };

  eventServiceMock.getEvent.mockResolvedValue({
    id: 1,
    title: 'AI Summit',
    description: 'Detailed event description',
    category: 'Technical',
    start_time: new Date(Date.now() + 3_600_000).toISOString(),
    end_time: new Date(Date.now() + 7_200_000).toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 50,
    seats_taken: 10,
    available_seats: 40,
    tags: [{ id: 5, name: 'Tech' }],
    owner_id: 9,
    owner_name: 'Organizer Name',
    recommendation_reason: 'Recommended for your profile',
    is_owner: false,
    is_registered: false,
    is_favorite: false,
    status: 'published',
    cover_url: '',
  });
  eventServiceMock.registerForEvent.mockResolvedValue(undefined);
  eventServiceMock.unregisterFromEvent.mockResolvedValue(undefined);
  eventServiceMock.resendRegistrationEmail.mockResolvedValue(undefined);
  eventServiceMock.addToFavorites.mockResolvedValue(undefined);
  eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
  eventServiceMock.cloneEvent.mockResolvedValue({ id: 77 });
  eventServiceMock.hideTag.mockResolvedValue(undefined);
  eventServiceMock.blockOrganizer.mockResolvedValue(undefined);
});
