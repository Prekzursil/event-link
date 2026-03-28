import React from 'react';
import { cleanup, fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useI18n } from '@/contexts/LanguageContext';
import { renderLanguageRoute, setEnglishPreference } from './page-test-helpers';

const {
  authState,
  eventServiceMock,
  navigateSpy,
  recordInteractionsSpy,
  toastSpy,
} = vi.hoisted(() => ({
  authState: {
    isAuthenticated: true,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  eventServiceMock: {
    addToFavorites: vi.fn(),
    blockOrganizer: vi.fn(),
    cloneEvent: vi.fn(),
    createEvent: vi.fn(),
    getEvent: vi.fn(),
    hideTag: vi.fn(),
    registerForEvent: vi.fn(),
    removeFromFavorites: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    suggestEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    updateEvent: vi.fn(),
  },
  navigateSpy: vi.fn(),
  recordInteractionsSpy: vi.fn(),
  toastSpy: vi.fn(),
}));

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/analytics.service', () => ({ recordInteractions: recordInteractionsSpy }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));
vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { AdminEventsTab } from '@/pages/admin/admin-dashboard/AdminEventsTab';
import { AdminUsersTab } from '@/pages/admin/admin-dashboard/AdminUsersTab';
import type { AdminDashboardController } from '@/pages/admin/admin-dashboard/useAdminDashboardController';
import { EventDetailOverview } from '@/pages/events/event-detail/EventDetailOverview';
import { useEventDetailController } from '@/pages/events/event-detail/useEventDetailController';
import { useEventFormController } from '@/pages/organizer/event-form/useEventFormController';
import type { EventDetail } from '@/types';

function makeEventDetail(overrides: Partial<EventDetail> = {}): EventDetail {
  return {
    id: 1,
    title: 'Coverage Event',
    description: 'Coverage description',
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
    owner_name: 'Organizer',
    recommendation_reason: 'Recommended for you',
    is_owner: false,
    is_registered: false,
    is_favorite: false,
    status: 'published',
    cover_url: '',
    ...overrides,
  };
}

function EventDetailOverviewHarness({ event }: { event: EventDetail }) {
  const { language, t } = useI18n();
  return (
    <EventDetailOverview
      event={event}
      isPast={false}
      isFull={false}
      language={language}
      t={t}
    />
  );
}

function EventDetailControllerHarness() {
  const controller = useEventDetailController();

  return (
    <>
      <button onClick={() => void controller.handleRegister()}>register</button>
      <button onClick={() => void controller.handleUnregister()}>unregister</button>
      <button onClick={() => void controller.handleResendRegistrationEmail()}>resend-email</button>
      <button onClick={() => void controller.handleFavorite()}>favorite</button>
      <button onClick={() => void controller.handleShare()}>share</button>
      <button onClick={controller.handleExportCalendar}>export</button>
      <button onClick={() => void controller.handleClone()}>clone</button>
      <button onClick={() => void controller.handleHideTag()}>hide-tag</button>
      <button onClick={() => void controller.handleBlockOrganizer()}>block-organizer</button>
    </>
  );
}

function EventFormControllerHarness() {
  const controller = useEventFormController();
  return <button onClick={controller.applySuggestion}>apply-suggestion</button>;
}

function AdminUsersTabHarness({ loadUsers }: { loadUsers: ReturnType<typeof vi.fn> }) {
  const { language, t } = useI18n();
  const controller = {
    handleUpdateUser: vi.fn(),
    isLoadingUsers: false,
    language,
    loadUsers,
    roleLabels: {
      admin: t.adminDashboard.roles.admin,
      organizator: t.adminDashboard.roles.organizer,
      student: t.adminDashboard.roles.student,
    },
    setUsersActive: vi.fn(),
    setUsersRole: vi.fn(),
    setUsersSearch: vi.fn(),
    t,
    totalUserPages: 3,
    users: [
      {
        id: 7,
        email: 'user@test.local',
        full_name: 'Test User',
        role: 'student',
        is_active: true,
        created_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
        registrations_count: 2,
        attended_count: 1,
        events_created_count: 0,
      },
    ],
    usersActive: 'all',
    usersPage: 2,
    usersRole: 'all',
    usersSearch: '',
    usersTotal: 50,
  } as unknown as AdminDashboardController;

  return <AdminUsersTab controller={controller} />;
}

function AdminEventsTabHarness() {
  const { language, t } = useI18n();
  const controller = {
    events: [
      {
        id: 11,
        title: 'Flagged Event',
        city: 'Cluj',
        start_time: new Date(Date.now() + 3_600_000).toISOString(),
        owner_email: 'owner@test.local',
        owner_name: 'Owner Name',
        status: 'published',
        moderation_status: 'flagged',
        moderation_flags: ['flag-1', 'flag-2', 'flag-3', 'flag-4'],
        moderation_score: 0.91,
        seats_taken: 9,
        max_seats: 20,
        deleted_at: null,
      },
      {
        id: 12,
        title: 'Clean Event',
        city: 'Iași',
        start_time: new Date(Date.now() + 7_200_000).toISOString(),
        owner_email: 'clean@test.local',
        owner_name: 'Clean Owner',
        status: 'draft',
        moderation_status: 'clean',
        moderation_score: 0.12,
        seats_taken: 2,
        max_seats: 10,
        deleted_at: null,
      },
    ],
    eventsFlaggedOnly: false,
    eventsIncludeDeleted: false,
    eventsPage: 1,
    eventsSearch: '',
    eventsStatus: 'all',
    eventsTotal: 1,
    handleDeleteEvent: vi.fn(),
    handleRestoreEvent: vi.fn(),
    handleReviewEvent: vi.fn(),
    isLoadingEvents: false,
    language,
    loadEvents: vi.fn(),
    reviewingEventId: null,
    setEventsFlaggedOnly: vi.fn(),
    setEventsIncludeDeleted: vi.fn(),
    setEventsSearch: vi.fn(),
    setEventsStatus: vi.fn(),
    t,
    totalEventPages: 1,
  } as unknown as AdminDashboardController;

  return <AdminEventsTab controller={controller} />;
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();

  Object.defineProperty(globalThis, 'open', {
    configurable: true,
    value: vi.fn(),
    writable: true,
  });
});

describe('coverage closure regressions', () => {
  it('covers the admin users previous-page handler', () => {
    const loadUsers = vi.fn();

    renderLanguageRoute(
      '/admin',
      '/admin',
      <AdminUsersTabHarness loadUsers={loadUsers} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(loadUsers).toHaveBeenCalledWith(1);
  });

  it('covers admin event moderation flag truncation', () => {
    renderLanguageRoute(
      '/admin',
      '/admin',
      <AdminEventsTabHarness />,
    );

    expect(screen.getByText('flag-1, flag-2, flag-3…')).toBeInTheDocument();
    expect(screen.queryByText('flag-1, flag-2, flag-3')).not.toBeInTheDocument();
  });

  it('covers the event detail overview no-tags branch', () => {
    renderLanguageRoute(
      '/',
      '/',
      <EventDetailOverviewHarness event={makeEventDetail({ tags: [] })} />,
    );

    expect(screen.queryByRole('heading', { name: /tags/i })).not.toBeInTheDocument();
  });

  it('covers event detail controller guard returns before data loads', async () => {
    renderLanguageRoute('/events', '/events', <EventDetailControllerHarness />);

    fireEvent.click(screen.getByRole('button', { name: 'register' }));
    fireEvent.click(screen.getByRole('button', { name: 'unregister' }));
    fireEvent.click(screen.getByRole('button', { name: 'resend-email' }));
    fireEvent.click(screen.getByRole('button', { name: 'favorite' }));
    fireEvent.click(screen.getByRole('button', { name: 'share' }));
    fireEvent.click(screen.getByRole('button', { name: 'export' }));
    fireEvent.click(screen.getByRole('button', { name: 'clone' }));
    fireEvent.click(screen.getByRole('button', { name: 'hide-tag' }));
    fireEvent.click(screen.getByRole('button', { name: 'block-organizer' }));
    await Promise.resolve();

    expect(eventServiceMock.registerForEvent).not.toHaveBeenCalled();
    expect(eventServiceMock.unregisterFromEvent).not.toHaveBeenCalled();
    expect(eventServiceMock.resendRegistrationEmail).not.toHaveBeenCalled();
    expect(eventServiceMock.addToFavorites).not.toHaveBeenCalled();
    expect(eventServiceMock.removeFromFavorites).not.toHaveBeenCalled();
    expect(globalThis.open).not.toHaveBeenCalled();
    expect(eventServiceMock.cloneEvent).not.toHaveBeenCalled();
    expect(eventServiceMock.hideTag).not.toHaveBeenCalled();
    expect(eventServiceMock.blockOrganizer).not.toHaveBeenCalled();
    expect(toastSpy).not.toHaveBeenCalled();
  });

  it('covers the event form apply-suggestion guard when no suggestion exists', () => {
    renderLanguageRoute(
      '/organizer/events/new',
      '/organizer/events/new',
      <EventFormControllerHarness />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'apply-suggestion' }));
    expect(toastSpy).not.toHaveBeenCalled();
  });
});
