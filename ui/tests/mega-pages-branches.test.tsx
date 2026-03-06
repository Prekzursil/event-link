import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';

const {
  toastSpy,
  navigateSpy,
  eventServiceMock,
  adminServiceMock,
  authServiceMock,
  authState,
  themeState,
} = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  eventServiceMock: {
    getEvent: vi.fn(),
    registerForEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    cloneEvent: vi.fn(),
    hideTag: vi.fn(),
    blockOrganizer: vi.fn(),
    getOrganizerEvents: vi.fn(),
    deleteEvent: vi.fn(),
    restoreEvent: vi.fn(),
    bulkUpdateEventStatus: vi.fn(),
    bulkUpdateEventTags: vi.fn(),
    getEventParticipants: vi.fn(),
    updateParticipantAttendance: vi.fn(),
    emailEventParticipants: vi.fn(),
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

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => themeState,
}));

vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);

vi.mock('@/components/ui/dropdown-menu', () =>
  import('./mock-component-modules').then((module) => module.createDropdownMenuMockModule()),
);

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage';
import { EventDetailPage } from '@/pages/events/EventDetailPage';
import { OrganizerDashboardPage } from '@/pages/organizer/OrganizerDashboardPage';
import { ParticipantsPage } from '@/pages/organizer/ParticipantsPage';
import { StudentProfilePage } from '@/pages/profile/StudentProfilePage';

function renderRoute(path: string, routePath: string, element: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LanguageProvider>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

function requireElement<T extends Element>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`Expected ${label}`);
  }
  return value;
}

function makeEventDetail(id: number) {
  return {
    id,
    title: `Event ${id}`,
    description: `Description ${id}`,
    category: 'Technical',
    start_time: new Date(Date.now() + 3600000).toISOString(),
    end_time: new Date(Date.now() + 7200000).toISOString(),
    city: 'Cluj',
    location: 'Main hall',
    max_seats: 40,
    seats_taken: 12,
    tags: [{ id: 5, name: 'Tech' }],
    owner_id: 77,
    owner_name: 'Org Name',
    recommendation_reason: 'Great match',
    is_owner: false,
    is_registered: false,
    available_seats: 28,
    is_favorite: false,
    status: 'published',
    cover_url: '',
  };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.setItem('language_preference', 'en');

  Object.defineProperty(globalThis, 'confirm', {
    writable: true,
    configurable: true,
    value: vi.fn().mockReturnValue(true),
  });

  Object.defineProperty(globalThis, 'open', {
    writable: true,
    configurable: true,
    value: vi.fn(),
  });

  Object.defineProperty(URL, 'createObjectURL', {
    writable: true,
    configurable: true,
    value: vi.fn().mockReturnValue('blob://csv'),
  });

  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { id: 1, role: 'student', email: 'student@test.local' };

  eventServiceMock.getEvent.mockResolvedValue(makeEventDetail(1));
  eventServiceMock.registerForEvent.mockResolvedValue(undefined);
  eventServiceMock.unregisterFromEvent.mockResolvedValue(undefined);
  eventServiceMock.resendRegistrationEmail.mockResolvedValue(undefined);
  eventServiceMock.cloneEvent.mockResolvedValue({ id: 88 });
  eventServiceMock.addToFavorites.mockResolvedValue(undefined);
  eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
  eventServiceMock.hideTag.mockResolvedValue(undefined);
  eventServiceMock.blockOrganizer.mockResolvedValue(undefined);

  eventServiceMock.getOrganizerEvents.mockResolvedValue([
    {
      id: 3,
      title: 'Organizer event',
      description: 'desc',
      category: 'Technical',
      start_time: new Date(Date.now() + 3600000).toISOString(),
      city: 'Cluj',
      location: 'Room 1',
      max_seats: 30,
      seats_taken: 3,
      tags: [],
      owner_id: 1,
      status: 'published',
    },
  ]);
  eventServiceMock.bulkUpdateEventStatus.mockResolvedValue({ updated: 1 });
  eventServiceMock.bulkUpdateEventTags.mockResolvedValue({ updated: 1 });
  eventServiceMock.deleteEvent.mockResolvedValue(undefined);
  eventServiceMock.restoreEvent.mockResolvedValue({ ok: true });

  eventServiceMock.getEventParticipants.mockResolvedValue({
    event_id: 3,
    title: 'Organizer event',
    seats_taken: 3,
    max_seats: 30,
    participants: [
      {
        id: 10,
        email: 'participant@test.local',
        full_name: 'Participant',
        registration_time: new Date().toISOString(),
        attended: false,
      },
    ],
    total: 40,
    page: 1,
    page_size: 20,
  });
  eventServiceMock.updateParticipantAttendance.mockResolvedValue(undefined);
  eventServiceMock.emailEventParticipants.mockResolvedValue({ recipients: 1 });

  eventServiceMock.getStudentProfile.mockResolvedValue({
    user_id: 1,
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
  ]);
  eventServiceMock.getPersonalizationSettings.mockResolvedValue({
    hidden_tags: [{ id: 4, name: 'Hidden' }],
    blocked_organizers: [{ id: 99, org_name: 'Muted Org', email: 'muted@test.local' }],
  });
  eventServiceMock.getNotificationPreferences.mockResolvedValue({
    email_digest_enabled: true,
    email_filling_fast_enabled: false,
  });
  eventServiceMock.getUniversityCatalog.mockResolvedValue([
    { name: 'UTCN', city: 'Cluj', faculties: ['Automatica', 'Informatica'] },
  ]);
  eventServiceMock.updateStudentProfile.mockResolvedValue({
    user_id: 1,
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
    total_users: 3,
    total_events: 2,
    total_registrations: 6,
    registrations_by_day: [{ date: '2026-03-01', registrations: 2 }],
    top_tags: [{ name: 'Tech', registrations: 4, events: 2 }],
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
        last_seen_at: new Date().toISOString(),
        registrations_count: 2,
        attended_count: 1,
        events_created_count: 0,
      },
    ],
    total: 24,
    page: 1,
    page_size: 20,
  });
  adminServiceMock.updateUser.mockResolvedValue({
    id: 1,
    email: 'student@test.local',
    full_name: 'Student Name',
    role: 'admin',
    is_active: true,
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
    registrations_count: 2,
    attended_count: 1,
    events_created_count: 0,
  });
  adminServiceMock.getEvents.mockResolvedValue({
    items: [
      {
        id: 21,
        title: 'Admin flagged',
        description: 'flagged',
        category: 'Technical',
        start_time: new Date().toISOString(),
        end_time: new Date(Date.now() + 3600000).toISOString(),
        status: 'published',
        owner_id: 7,
        owner_email: 'org@test.local',
        owner_name: 'Organizer',
        seats_taken: 1,
        max_seats: 50,
        city: 'Cluj',
        location: 'Hall',
        tags: [],
        moderation_status: 'flagged',
        moderation_score: 0.91,
        moderation_flags: ['spam'],
        deleted_at: null,
      },
      {
        id: 22,
        title: 'Admin deleted',
        description: 'deleted',
        category: 'Technical',
        start_time: new Date().toISOString(),
        end_time: new Date(Date.now() + 3600000).toISOString(),
        status: 'draft',
        owner_id: 8,
        owner_email: 'org2@test.local',
        owner_name: 'Organizer2',
        seats_taken: 0,
        max_seats: 30,
        city: 'Iasi',
        location: 'Room 10',
        tags: [],
        moderation_status: 'clean',
        moderation_score: null,
        moderation_flags: [],
        deleted_at: new Date().toISOString(),
      },
    ],
    total: 24,
    page: 1,
    page_size: 20,
  });
  adminServiceMock.reviewEventModeration.mockResolvedValue({ ok: true });
  adminServiceMock.getPersonalizationMetrics.mockResolvedValue({
    items: [{ date: '2026-03-01', impressions: 40, clicks: 10, registrations: 3, ctr: 0.25, registration_conversion: 0.3 }],
    totals: { impressions: 40, clicks: 10, registrations: 3, ctr: 0.25, registration_conversion: 0.3 },
  });
  adminServiceMock.enqueueRecommendationsRetrain.mockResolvedValue({ job_id: 1, job_type: 'retrain', status: 'queued' });
  adminServiceMock.enqueueWeeklyDigest.mockResolvedValue({ job_id: 2, job_type: 'digest', status: 'queued' });
  adminServiceMock.enqueueFillingFast.mockResolvedValue({ job_id: 3, job_type: 'filling-fast', status: 'queued' });

  authServiceMock.updateThemePreference.mockResolvedValue(undefined);
  authServiceMock.updateLanguagePreference.mockResolvedValue(undefined);
  authState.refreshUser.mockResolvedValue(undefined);
  authState.logout.mockResolvedValue(undefined);
});

describe('mega pages branch matrix', () => {
  it('covers admin dashboard queue/users/events action branches', async () => {
    renderRoute('/admin', '/admin', <AdminDashboardPage />);
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole('button', { name: /Retrain/i }));
    await waitFor(() => expect(adminServiceMock.enqueueRecommendationsRetrain).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole('button', { name: /Digest/i }));
    await waitFor(() => expect(adminServiceMock.enqueueWeeklyDigest).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole('button', { name: /Filling-fast/i }));
    await waitFor(() => expect(adminServiceMock.enqueueFillingFast).toHaveBeenCalled());

    const usersTab = screen.getByRole('tab', { name: /Users/i });
    fireEvent.mouseDown(usersTab);
    fireEvent.click(usersTab);
    await waitFor(() => expect(usersTab).toHaveAttribute('data-state', 'active'));
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalledTimes(2));

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[checkboxes.length - 1]);
    await waitFor(() => expect(adminServiceMock.updateUser).toHaveBeenCalled());

    const eventsTab = screen.getByRole('tab', { name: /Events/i });
    fireEvent.mouseDown(eventsTab);
    fireEvent.click(eventsTab);
    await waitFor(() => expect(eventsTab).toHaveAttribute('data-state', 'active'));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole('button', { name: /Mark reviewed/i }));
    await waitFor(() => expect(adminServiceMock.reviewEventModeration).toHaveBeenCalledWith(21));

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    await waitFor(() => expect(eventServiceMock.deleteEvent).toHaveBeenCalledWith(21));

    fireEvent.click(screen.getByRole('button', { name: /Restore/i }));
    await waitFor(() => expect(eventServiceMock.restoreEvent).toHaveBeenCalledWith(22));
  }, 15000);

  it('covers event detail unauthenticated redirect and registered flows', async () => {
    authState.isAuthenticated = false;
    authState.user = null;
    renderRoute('/events/1', '/events/:id', <EventDetailPage />);

    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/login', { state: { from: { pathname: '/events/1' } } }));

    cleanup();
    authState.isAuthenticated = true;
    authState.user = { id: 1, role: 'student', email: 'student@test.local' };
    eventServiceMock.getEvent.mockResolvedValueOnce({ ...makeEventDetail(1), is_registered: true, is_favorite: true });
    renderRoute('/events/1', '/events/:id', <EventDetailPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: /Resend confirmation email/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(eventServiceMock.resendRegistrationEmail).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Unregister/i }));
    await waitFor(() => expect(eventServiceMock.unregisterFromEvent).toHaveBeenCalledWith(1));
  });

  it('covers organizer dashboard bulk actions and participants email/csv/sort flows', async () => {
    renderRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

    const organizerCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(organizerCheckboxes[0]);
    fireEvent.click(screen.getByRole('button', { name: /Publish/i }));
    await waitFor(() => expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'));

    cleanup();
    renderRoute('/organizer/events/3/participants', '/organizer/events/:id/participants', <ParticipantsPage />);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'));

    fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Subject/i), { target: { value: 'Hello participants' } });
    fireEvent.change(screen.getByLabelText(/Message/i), { target: { value: 'Thanks for joining.' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(eventServiceMock.emailEventParticipants).toHaveBeenCalledWith(3, 'Hello participants', 'Thanks for joining.'));

    fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));
    expect(URL.createObjectURL).toHaveBeenCalled();

    eventServiceMock.updateParticipantAttendance.mockRejectedValueOnce(new Error('attendance-fail'));
    const participantCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Registration date/i }));
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'desc'));
  });

  it('covers admin dashboard error branches, callbacks and pagination controls', async () => {
    adminServiceMock.getStats.mockRejectedValueOnce(new Error('stats-fail'));
    adminServiceMock.getPersonalizationMetrics.mockRejectedValueOnce(new Error('metrics-fail'));
    adminServiceMock.getUsers.mockRejectedValueOnce(new Error('users-fail'));
    adminServiceMock.getEvents.mockRejectedValueOnce(new Error('events-fail'));
    adminServiceMock.enqueueRecommendationsRetrain.mockRejectedValueOnce(new Error('retrain-fail'));
    adminServiceMock.enqueueWeeklyDigest.mockRejectedValueOnce(new Error('digest-fail'));
    adminServiceMock.enqueueFillingFast.mockRejectedValueOnce(new Error('filling-fail'));

    renderRoute('/admin', '/admin', <AdminDashboardPage />);
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Reload/i }));
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole('button', { name: /Retrain/i }));
    fireEvent.click(screen.getByRole('button', { name: /Digest/i }));
    fireEvent.click(screen.getByRole('button', { name: /Filling-fast/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    const usersTab = screen.getByRole('tab', { name: /Users/i });
    fireEvent.mouseDown(usersTab);
    fireEvent.click(usersTab);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/email \/ name|email \/ nume/i), { target: { value: 'student' } });
    fireEvent.click(screen.getByRole('button', { name: /^Admin$/i }));
    fireEvent.click(screen.getByRole('button', { name: /Inactive/i }));
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());

    adminServiceMock.updateUser.mockRejectedValueOnce(new Error('update-user-fail'));
    const usersRow = screen.getByText('student@test.local').closest('tr');
    fireEvent.click(within(requireElement(usersRow, 'users row')).getByRole('button', { name: /Admin/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    adminServiceMock.getUsers.mockResolvedValueOnce({
      items: [{
        id: 1,
        email: 'student@test.local',
        full_name: 'Student Name',
        role: 'student',
        is_active: true,
        created_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
        registrations_count: 2,
        attended_count: 1,
        events_created_count: 0,
      }],
      total: 40,
      page: 2,
      page_size: 20,
    });

    const usersNextButton = screen.getByRole('button', { name: /Next|Urm|Înainte/i });
    fireEvent.click(usersNextButton);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })));

    await waitFor(() => expect(screen.queryByText(/Loading users|Se încarcă utilizatorii/i)).not.toBeInTheDocument());
    const usersPrevButton = screen.getByRole('button', { name: /Back|Prev|Previous|Înapoi|Anterior/i });
    fireEvent.click(usersPrevButton);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })));

    const eventsTab = screen.getByRole('tab', { name: /Events/i });
    fireEvent.mouseDown(eventsTab);
    fireEvent.click(eventsTab);
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/title \/ owner|titlu \/ owner/i), { target: { value: 'flagged' } });
    fireEvent.click(screen.getByRole('button', { name: /Draft/i }));
    const eventsCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(eventsCheckboxes[eventsCheckboxes.length - 2]);
    fireEvent.click(eventsCheckboxes[eventsCheckboxes.length - 1]);
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());

    adminServiceMock.getEvents.mockResolvedValueOnce({
      items: [{
        id: 21,
        title: 'Admin flagged',
        description: 'flagged',
        category: 'Technical',
        start_time: new Date().toISOString(),
        end_time: new Date(Date.now() + 3600000).toISOString(),
        status: 'published',
        owner_id: 7,
        owner_email: 'org@test.local',
        owner_name: 'Organizer',
        seats_taken: 1,
        max_seats: 50,
        city: 'Cluj',
        location: 'Hall',
        tags: [],
        moderation_status: 'flagged',
        moderation_score: 0.91,
        moderation_flags: ['spam'],
        deleted_at: null,
      }],
      total: 40,
      page: 2,
      page_size: 20,
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })));
    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })));

    adminServiceMock.reviewEventModeration.mockRejectedValueOnce(new Error('review-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Mark reviewed/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.restoreEvent.mockRejectedValueOnce(new Error('restore-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Restore/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers organizer and participants callback edge branches', async () => {
    renderRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

    const organizerCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);
    fireEvent.click(screen.getByRole('button', { name: /Publish|Public/i }));
    await waitFor(() => expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'));

    fireEvent.click(organizerCheckboxes[0]);
    fireEvent.click(organizerCheckboxes[0]);
    fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);

    eventServiceMock.bulkUpdateEventStatus.mockRejectedValueOnce(new Error('bulk-status-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Publish/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Clear selection/i }));

    fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);
    fireEvent.click(screen.getByRole('button', { name: /Set tags/i }));
    fireEvent.change(screen.getByPlaceholderText(/Add a tag/i), { target: { value: 'bulk-tag' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/i }));
    eventServiceMock.bulkUpdateEventTags.mockRejectedValueOnce(new Error('bulk-tags-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));

    vi.mocked(globalThis.confirm).mockReturnValueOnce(true);
    eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    vi.mocked(globalThis.confirm).mockReturnValueOnce(false);
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    expect(eventServiceMock.deleteEvent).toHaveBeenCalledTimes(1);

    vi.mocked(globalThis.confirm).mockReturnValueOnce(true);
    eventServiceMock.deleteEvent.mockResolvedValueOnce(undefined);
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    await waitFor(() => expect(eventServiceMock.deleteEvent).toHaveBeenCalledWith(3));

    cleanup();
    eventServiceMock.getEventParticipants.mockRejectedValueOnce(new Error('participants-load-fail'));
    renderRoute('/organizer/events/3/participants', '/organizer/events/:id/participants', <ParticipantsPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEventParticipants.mockResolvedValue({
      event_id: 3,
      title: 'Organizer event',
      seats_taken: 3,
      max_seats: 30,
      participants: [{
        id: 10,
        email: 'participant@test.local',
        full_name: 'Participant',
        registration_time: new Date().toISOString(),
        attended: false,
      }],
      total: 40,
      page: 1,
      page_size: 20,
    });
    renderRoute('/organizer/events/3/participants', '/organizer/events/:id/participants', <ParticipantsPage />);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'));

    fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
    const emailOpenDialog = await screen.findByRole('dialog');
    fireEvent.click(within(emailOpenDialog).getByRole('button', { name: /Cancel/i }));
    const participantsTable = screen.getByRole('table');
    const participantsSortButtons = within(participantsTable).getAllByRole('button');
    fireEvent.click(participantsSortButtons[0]);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'email', 'asc'));

    fireEvent.click(participantsSortButtons[1]);
    fireEvent.click(participantsSortButtons[2]);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalled());
    const participantsPageText = screen.getAllByText(/Page/i).find((node) => /of/i.test(node.textContent || '')) ?? null;
    expect(participantsPageText).not.toBeNull();
    const participantsPageContainer = participantsPageText?.closest('div')?.parentElement;
    const participantsPagerButtons = within(requireElement(participantsPageContainer, 'participants page container')).getAllByRole('button');
    fireEvent.click(participantsPagerButtons[participantsPagerButtons.length - 1]);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 2, 20, 'registration_time', 'asc'));
    fireEvent.click(participantsPagerButtons[participantsPagerButtons.length - 2]);
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'));

    await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(0));

    const participantsCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(participantsCheckboxes[participantsCheckboxes.length - 1]);
    await waitFor(() => expect(eventServiceMock.updateParticipantAttendance).toHaveBeenCalledWith(3, 10, true));

    fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Subject/i), { target: { value: 'Subject' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Message/i), { target: { value: 'Body' } });
    eventServiceMock.emailEventParticipants.mockRejectedValueOnce(new Error('email-fail'));
    fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(within(dialog).getByRole('button', { name: /Cancel/i }));

    fireEvent.click(screen.getByRole('button', { name: /^50$/i }));
    await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 50, 'registration_time', 'asc'));

    const paginationText = screen.queryByText(/Page/i);
    if (paginationText) {
      const paginationContainer = paginationText.closest('div');
      if (paginationContainer) {
        const paginationButtons = within(paginationContainer).getAllByRole('button');
        fireEvent.click(paginationButtons[paginationButtons.length - 1]);
        await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 2, 50, 'registration_time', 'asc'));
        fireEvent.click(paginationButtons[0]);
        await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 50, 'registration_time', 'asc'));
      }
    }

    fireEvent.click(screen.getByRole('button', { name: /Back to dashboard/i }));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');
  }, 25000);

  it('covers student profile save/export/delete and personalization branches', async () => {
    renderRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Export data/i }));
    await waitFor(() => expect(eventServiceMock.exportMyData).toHaveBeenCalled());

    const unblock = screen.getByRole('button', { name: /Unblock/i });
    fireEvent.click(unblock);
    await waitFor(() => expect(eventServiceMock.unblockOrganizer).toHaveBeenCalledWith(99));

    fireEvent.click(screen.getByRole('button', { name: /Delete account/i }));
    const dialog = await screen.findByRole('dialog');
    const destructiveButtons = within(dialog).getAllByRole('button', { name: /Delete account/i });
    fireEvent.click(destructiveButtons[0]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Access code/i), { target: { value: 'secret-access-code' } });
    fireEvent.click(destructiveButtons[0]);
    await waitFor(() => expect(eventServiceMock.deleteMyAccount).toHaveBeenCalledWith('secret-access-code'));
    expect(authState.logout).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith('/');
  });
  it('covers users previous-page handler and organizer deselection branch', async () => {
    adminServiceMock.getUsers.mockResolvedValueOnce({
      items: [{
        id: 1,
        email: 'student@test.local',
        full_name: 'Student Name',
        role: 'student',
        is_active: true,
        created_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
        registrations_count: 2,
        attended_count: 1,
        events_created_count: 0,
      }],
      total: 40,
      page: 2,
      page_size: 20,
    });

    renderRoute('/admin', '/admin', <AdminDashboardPage />);
    const usersTab = await screen.findByRole('tab', { name: /Users/i });
    fireEvent.mouseDown(usersTab);
    fireEvent.click(usersTab);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());

    const usersPrevButtons = await screen.findAllByRole('button', { name: /Back|Prev|Previous|Înapoi|Anterior/i });
    usersPrevButtons.forEach((button) => {
      if (!button.hasAttribute('disabled')) {
        fireEvent.click(button);
      }
    });
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })));

    cleanup();
    renderRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

    const organizerCheckboxes = screen.getAllByRole('checkbox');
    const rowCheckbox = organizerCheckboxes[organizerCheckboxes.length - 1];
    fireEvent.click(rowCheckbox);
    await waitFor(() => expect(screen.getByRole('button', { name: /Publish|Public/i })).toBeInTheDocument());

    fireEvent.click(rowCheckbox);
    await waitFor(() => expect(screen.queryByRole('button', { name: /Publish|Public/i })).not.toBeInTheDocument());
  }, 20000);

});


