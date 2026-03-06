import React from 'react';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { defineMutableValue, renderLanguageRoute, setEnglishPreference } from './page-test-helpers';

const {
  toastSpy,
  navigateSpy,
  recordInteractionsSpy,
  eventServiceMock,
  adminServiceMock,
  authServiceMock,
  authState,
  themeState,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  recordInteractionsSpy: vi.fn(),
  eventServiceMock: {
    getEvents: vi.fn(),
    getFavorites: vi.fn(),
    getEvent: vi.fn(),
    registerForEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    getOrganizerEvents: vi.fn(),
    deleteEvent: vi.fn(),
    restoreEvent: vi.fn(),
    cloneEvent: vi.fn(),
    suggestEvent: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
    bulkUpdateEventStatus: vi.fn(),
    bulkUpdateEventTags: vi.fn(),
    getEventParticipants: vi.fn(),
    updateParticipantAttendance: vi.fn(),
    emailEventParticipants: vi.fn(),
    getOrganizerProfile: vi.fn(),
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
    hideTag: vi.fn(),
    blockOrganizer: vi.fn(),
    getMyCalendar: vi.fn(),
  },
  adminServiceMock: {
    getStats: vi.fn(),
    getUsers: vi.fn(),
    updateUser: vi.fn(),
    getEvents: vi.fn(),
    reviewEventModeration: vi.fn(),
    getPersonalizationMetrics: vi.fn(),
    enqueueRecommendationsRetrain: vi.fn(),
    enqueueWeeklyDigest: vi.fn(),
    enqueueFillingFast: vi.fn(),
  },
  authServiceMock: {
    updateThemePreference: vi.fn(),
    updateLanguagePreference: vi.fn(),
  },
  authState: {
    isAuthenticated: true,
    isOrganizer: true,
    isAdmin: true,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  themeState: {
    preference: 'system',
    setPreference: vi.fn(),
  },
}));

vi.mock('@/services/event.service', () => ({
  default: eventServiceMock,
}));

vi.mock('@/services/admin.service', () => ({
  default: adminServiceMock,
}));

vi.mock('@/services/auth.service', () => ({
  default: authServiceMock,
}));

vi.mock('@/services/analytics.service', () => ({
  recordInteractions: recordInteractionsSpy,
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => themeState,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { EventsPage } from '@/pages/events/EventsPage';
import { EventDetailPage } from '@/pages/events/EventDetailPage';
import { OrganizerDashboardPage } from '@/pages/organizer/OrganizerDashboardPage';
import { EventFormPage } from '@/pages/organizer/EventFormPage';
import { ParticipantsPage } from '@/pages/organizer/ParticipantsPage';
import { OrganizerProfilePage } from '@/pages/organizer/OrganizerProfilePage';
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage';
import { StudentProfilePage } from '@/pages/profile/StudentProfilePage';

function makeEvent(id: number, startOffsetDays: number) {
  const start = new Date();
  start.setDate(start.getDate() + startOffsetDays);
  const end = new Date(start.getTime() + 60 * 60 * 1000);

  return {
    id,
    title: `Event ${id}`,
    description: `Description ${id}`,
    category: 'Technical',
    start_time: start.toISOString(),
    end_time: end.toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 50,
    seats_taken: 5,
    tags: [{ id: 1, name: 'Tech' }, { id: 2, name: 'Community' }],
    status: 'published',
    cover_url: '',
    recommendation_reason: 'Popular in your area',
  };
}

function makeEventDetail(id: number) {
  return {
    ...makeEvent(id, 2),
    owner_id: 7,
    owner_name: 'Organizer Name',
    is_owner: false,
    is_registered: false,
    is_favorite: false,
    available_seats: 45,
  };
}

describe('mega pages smoke coverage', () => {
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

    defineMutableValue(navigator, 'clipboard', {
      writeText: vi.fn().mockResolvedValue(undefined),
    });
    defineMutableValue(globalThis, 'open', vi.fn());
    defineMutableValue(globalThis, 'confirm', vi.fn().mockReturnValue(true));
    defineMutableValue(URL, 'createObjectURL', vi.fn().mockReturnValue('blob://mock-file'));

    authState.isAuthenticated = true;
    authState.isOrganizer = true;
    authState.isAdmin = true;
    authState.user = { id: 1, role: 'student', email: 'student@test.local' };

    const listEvents = [makeEvent(1, 2), makeEvent(2, -1)];
    eventServiceMock.getEvents.mockResolvedValue({
      items: listEvents,
      total: listEvents.length,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    eventServiceMock.getFavorites.mockResolvedValue({ items: [listEvents[0]] });

    eventServiceMock.getEvent.mockResolvedValue(makeEventDetail(1));
    eventServiceMock.registerForEvent.mockResolvedValue(undefined);
    eventServiceMock.unregisterFromEvent.mockResolvedValue(undefined);
    eventServiceMock.resendRegistrationEmail.mockResolvedValue(undefined);
    eventServiceMock.addToFavorites.mockResolvedValue(undefined);
    eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
    eventServiceMock.cloneEvent.mockResolvedValue({ id: 88 });
    eventServiceMock.hideTag.mockResolvedValue(undefined);
    eventServiceMock.blockOrganizer.mockResolvedValue(undefined);

    eventServiceMock.getOrganizerEvents.mockResolvedValue([makeEvent(3, 3)]);
    eventServiceMock.deleteEvent.mockResolvedValue(undefined);
    eventServiceMock.restoreEvent.mockResolvedValue({ status: 'ok' });
    eventServiceMock.bulkUpdateEventStatus.mockResolvedValue({ updated: 1 });
    eventServiceMock.bulkUpdateEventTags.mockResolvedValue({ updated: 1 });

    eventServiceMock.suggestEvent.mockResolvedValue({
      suggested_category: 'Technical',
      suggested_tags: ['AI'],
      suggested_city: 'Cluj',
      confidence: 0.9,
      reason: 'fits',
    });
    eventServiceMock.createEvent.mockResolvedValue(makeEvent(9, 5));
    eventServiceMock.updateEvent.mockResolvedValue(makeEvent(10, 7));

    eventServiceMock.getEventParticipants.mockResolvedValue({
      event_id: 3,
      title: 'Event 3',
      participants: [
        {
          id: 91,
          email: 'participant@test.local',
          full_name: 'Participant Name',
          registration_time: new Date().toISOString(),
          attended: false,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
    eventServiceMock.updateParticipantAttendance.mockResolvedValue(undefined);
    eventServiceMock.emailEventParticipants.mockResolvedValue({ recipients: 1 });

    eventServiceMock.getOrganizerProfile.mockResolvedValue({
      id: 7,
      full_name: 'Organizer Name',
      org_name: 'Organizer Team',
      org_logo_url: '',
      org_description: 'Organizer profile',
      org_website: 'https://example.org',
      email: 'org@test.local',
      events: [makeEvent(11, 2), makeEvent(12, -2)],
    });

    eventServiceMock.getStudentProfile.mockResolvedValue({
      email: 'student@test.local',
      full_name: 'Student Name',
      city: 'Cluj',
      university: 'UTCN',
      faculty: 'Automatica',
      study_level: 'bachelor',
      study_year: 2,
      interest_tags: [{ id: 1, name: 'Muzică' }],
    });
    eventServiceMock.getAllTags.mockResolvedValue([
      { id: 1, name: 'Muzică' },
      { id: 2, name: 'Tech' },
      { id: 3, name: 'Community' },
    ]);
    eventServiceMock.getPersonalizationSettings.mockResolvedValue({
      hidden_tags: [{ id: 4, name: 'Hidden' }],
      blocked_organizers: [{ id: 99, org_name: 'Muted Org', full_name: 'Muted Organizer' }],
    });
    eventServiceMock.getNotificationPreferences.mockResolvedValue({
      email_digest_enabled: true,
      email_filling_fast_enabled: false,
    });
    eventServiceMock.getUniversityCatalog.mockResolvedValue([
      { name: 'UTCN', city: 'Cluj', faculties: ['Automatica', 'Informatica'] },
    ]);
    eventServiceMock.updateStudentProfile.mockResolvedValue({
      email: 'student@test.local',
      full_name: 'Student Name Updated',
      city: 'Cluj',
      university: 'UTCN',
      faculty: 'Automatica',
      study_level: 'bachelor',
      study_year: 2,
      interest_tags: [{ id: 2, name: 'Tech' }],
    });
    eventServiceMock.updateNotificationPreferences.mockResolvedValue({
      email_digest_enabled: false,
      email_filling_fast_enabled: true,
    });
    eventServiceMock.unhideTag.mockResolvedValue(undefined);
    eventServiceMock.unblockOrganizer.mockResolvedValue(undefined);
    eventServiceMock.exportMyData.mockResolvedValue(new Blob(['{"ok":true}'], { type: 'application/json' }));
    eventServiceMock.deleteMyAccount.mockResolvedValue(undefined);

    adminServiceMock.getStats.mockResolvedValue({
      users_total: 1,
      users_active: 1,
      users_students: 1,
      users_organizers: 0,
      users_admins: 0,
      events_total: 1,
      events_published: 1,
      events_draft: 0,
      registrations_total: 1,
      registrations_last_30_days: 1,
      top_tags: [{ tag: 'Tech', count: 1 }],
    });
    adminServiceMock.getUsers.mockResolvedValue({
      items: [
        {
          id: 1,
          email: 'student@test.local',
          full_name: 'Student Name',
          role: 'student',
          is_active: true,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
    adminServiceMock.updateUser.mockResolvedValue({
      id: 1,
      email: 'student@test.local',
      full_name: 'Student Name',
      role: 'student',
      is_active: true,
      created_at: new Date().toISOString(),
    });
    adminServiceMock.getEvents.mockResolvedValue({
      items: [
        {
          id: 21,
          title: 'Admin Event',
          status: 'published',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          owner_id: 7,
          owner_email: 'org@test.local',
          owner_name: 'Organizer',
          seats_taken: 1,
          max_seats: 50,
          city: 'Cluj',
          location: 'Hall',
          tags: [],
          moderation_flagged: false,
          moderation_last_scored_at: null,
          moderation_score_max: null,
          moderation_categories: [],
          deleted_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
    adminServiceMock.reviewEventModeration.mockResolvedValue({ status: 'ok' });
    adminServiceMock.getPersonalizationMetrics.mockResolvedValue({
      from: '2026-01-01T00:00:00Z',
      to: '2026-01-31T00:00:00Z',
      hidden_tags_count: 0,
      blocked_organizers_count: 0,
      interactions_count: 0,
      recommendation_impressions_count: 0,
      recommendation_clicks_count: 0,
      recommendation_ctr: 0,
      recommendation_ctr_delta: 0,
      top_hidden_tags: [],
      top_blocked_organizers: [],
    });
    adminServiceMock.enqueueRecommendationsRetrain.mockResolvedValue({ job_id: 'job-1', status: 'queued' });
    adminServiceMock.enqueueWeeklyDigest.mockResolvedValue({ job_id: 'job-2', status: 'queued' });
    adminServiceMock.enqueueFillingFast.mockResolvedValue({ job_id: 'job-3', status: 'queued' });

    authServiceMock.updateThemePreference.mockResolvedValue(undefined);
    authServiceMock.updateLanguagePreference.mockResolvedValue(undefined);
    authState.refreshUser.mockResolvedValue(undefined);
    authState.logout.mockResolvedValue(undefined);
  });

  it('covers events listing and detail flows', async () => {
    renderLanguageRoute('/events?search=tech', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    expect(await screen.findByText(/Event 1/i)).toBeInTheDocument();

    cleanup();
    renderLanguageRoute('/events/1', '/events/:id', <EventDetailPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Register/i }));
    await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Add to calendar/i }));
    expect(globalThis.open).toHaveBeenCalled();
  }, 15000);

  it('covers events page and event detail error branches', async () => {
    eventServiceMock.getEvents.mockRejectedValueOnce(new Error('events-fail'));
    renderLanguageRoute('/events', '/events', <EventsPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvent.mockRejectedValueOnce(new Error('event-fail'));
    renderLanguageRoute('/events/1', '/events/:id', <EventDetailPage />);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/'));
  });

  it('covers organizer pages basic success flows', async () => {
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());
    expect(await screen.findByText(/Event 3/i)).toBeInTheDocument();

    cleanup();
    renderLanguageRoute('/organizer/events/3/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(3));

    cleanup();
    renderLanguageRoute('/organizer/events/3/participants', '/organizer/events/:id/participants', <ParticipantsPage />);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'));

    cleanup();
    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/Organizer Team/i)).toBeInTheDocument();
  });

  it('covers organizer page error branches', async () => {
    eventServiceMock.getOrganizerEvents.mockRejectedValueOnce(new Error('org-events-fail'));
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getOrganizerProfile.mockRejectedValueOnce(new Error('org-profile-fail'));
    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(screen.getByText(/Organizer not found/i)).toBeInTheDocument());
  });

  it('covers admin dashboard loading and tab-driven fetches', async () => {
    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);

    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());
    await waitFor(() => expect(adminServiceMock.getPersonalizationMetrics).toHaveBeenCalled());

    const tabs = await screen.findAllByRole('tab');
    fireEvent.click(tabs[1]);
    fireEvent.click(tabs[2]);
    expect(tabs).toHaveLength(3);
  });

  it('covers student profile load and primary actions', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
    await waitFor(() => expect(eventServiceMock.getAllTags).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Export data/i }));
    await waitFor(() => expect(eventServiceMock.exportMyData).toHaveBeenCalled());
  });
});

