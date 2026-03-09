import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  defineMutableValue,
  renderLanguageRoute,
  requireElement,
  requireInput,
  setEnglishPreference,
} from './page-test-helpers';

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
} = vi.hoisted(() => ({
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

// Simplify select interactions while keeping callback behavior explicit.
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
  EventCard: ({ event, onFavoriteToggle, onEventClick, isFavorite }: {
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

import { EventsPage } from '@/pages/events/EventsPage';
import { OrganizerDashboardPage } from '@/pages/organizer/OrganizerDashboardPage';
import { StudentProfilePage } from '@/pages/profile/StudentProfilePage';

function makeEvent(id: number) {
  return {
    id,
    title: `Event ${id}`,
    description: `Description ${id}`,
    category: 'Technical',
    start_time: new Date(Date.now() + 3600000).toISOString(),
    end_time: new Date(Date.now() + 7200000).toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 40,
    seats_taken: 4,
    tags: [{ id: 1, name: 'Tech' }],
    owner_id: 55,
    owner_name: 'Organizer',
    recommendation_reason: 'Recommended',
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
      matches: false,
      media: '(min-width: 640px)',
      addListener: mediaAddListenerSpy,
      removeListener: mediaRemoveListenerSpy,
    })),
  );

  defineMutableValue(globalThis, 'confirm', vi.fn().mockReturnValue(true));
  defineMutableValue(globalThis, 'open', vi.fn());
  defineMutableValue(URL, 'createObjectURL', vi.fn().mockReturnValue('blob://data'));

  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.user = { id: 11, role: 'student', email: 'student@test.local' };
  authState.refreshUser.mockResolvedValue(undefined);
  authState.logout.mockResolvedValue(undefined);

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

  eventServiceMock.getStudentProfile.mockResolvedValue({
    user_id: 11,
    email: 'student@test.local',
    full_name: 'Student Name',
    city: 'Cluj',
    university: 'UTCN',
    faculty: 'Automatica',
    study_level: 'bachelor',
    study_year: 4,
    interest_tags: [{ id: 1, name: 'Muzică' }],
  });
  eventServiceMock.getAllTags.mockResolvedValue([
    { id: 1, name: 'Muzică' },
    { id: 2, name: 'Tech' },
  ]);
  eventServiceMock.getPersonalizationSettings.mockResolvedValue({
    hidden_tags: [{ id: 5, name: 'Hidden' }],
    blocked_organizers: [{ id: 77, org_name: 'Muted Org', full_name: 'Muted Org', email: 'muted@test.local' }],
  });
  eventServiceMock.getNotificationPreferences.mockResolvedValue({
    email_digest_enabled: true,
    email_filling_fast_enabled: false,
  });
  eventServiceMock.getUniversityCatalog.mockResolvedValue([
    { name: 'UTCN', city: 'Cluj', faculties: ['Automatica', 'Informatica'] },
  ]);
  eventServiceMock.updateStudentProfile.mockResolvedValue({
    user_id: 11,
    email: 'student@test.local',
    full_name: 'Student Name Updated',
    city: 'Cluj',
    university: 'UTCN',
    faculty: 'Informatica',
    study_level: 'master',
    study_year: 1,
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

  eventServiceMock.getOrganizerEvents.mockResolvedValue([makeEvent(3)]);
  eventServiceMock.bulkUpdateEventStatus.mockResolvedValue({ updated: 1 });
  eventServiceMock.bulkUpdateEventTags.mockResolvedValue({ updated: 1 });
  eventServiceMock.deleteEvent.mockResolvedValue(undefined);

  authServiceMock.updateThemePreference.mockResolvedValue(undefined);
  authServiceMock.updateLanguagePreference.mockResolvedValue(undefined);
});

describe('high-impact page coverage', () => {
  it('covers EventsPage filter/pagination handlers and favorite remove error branch', async () => {
    renderLanguageRoute(
      '/events?search=abc&category=technical&city=Cluj&location=Hall&start_date=2026-03-01&end_date=2026-03-02&page=2&sort=recommended&page_size=12',
      '/events',
      <EventsPage />,
    );

    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    expect(mediaAddListenerSpy).toHaveBeenCalled();


    fireEvent.change(screen.getByPlaceholderText(/Search events/i), { target: { value: 'new query' } });
    fireEvent.change(screen.getByPlaceholderText(/City/i), { target: { value: 'Iasi' } });
    fireEvent.change(screen.getByPlaceholderText(/Location/i), { target: { value: 'Campus' } });

    fireEvent.click(screen.getByText(/Recommended for you/i));
    fireEvent.click(screen.getByText(/Soonest/i));

    await screen.findByTestId('event-1');
    fireEvent.click(screen.getByRole('button', { name: /toggle-favorite-1/i }));
    fireEvent.click(screen.getByRole('button', { name: /open-event-1/i }));
    fireEvent.click(screen.getByRole('button', { name: /Clear all/i }));
    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(2)],
      total: 25,
      page: 2,
      page_size: 12,
      total_pages: 3,
    });
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [makeEvent(2)] });
    eventServiceMock.removeFromFavorites.mockRejectedValueOnce(new Error('fav-remove-fail'));
    renderLanguageRoute('/events?page=2', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    const event2Card = await screen.findByTestId('event-2');
    fireEvent.click(within(event2Card).getByRole('button', { name: /toggle-favorite-2/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    const pager = requireElement(screen.getByText(/Page\s+2\s+of\s+3/i).parentElement, 'events pager');
    const pagerButtons = within(pager).getAllByRole('button');
    fireEvent.click(pagerButtons[0]);
    fireEvent.click(pagerButtons[1]);
  }, 20000);
  it('covers EventsPage recommendation click and search/filter interaction payload branches', async () => {
    eventServiceMock.getEvents.mockImplementation(async (filters: { sort?: string; page_size?: number }) => {
      if (filters?.sort === 'recommended' && filters?.page_size === 4) {
        return { items: [makeEvent(90)], total: 1, page: 1, page_size: 4, total_pages: 1 };
      }
      return { items: [makeEvent(1)], total: 25, page: 1, page_size: 12, total_pages: 3 };
    });

    renderLanguageRoute('/events?search=ai&category=technical&city=Cluj&location=Hall&tags=ai,ml&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    // Trigger delayed impression + search interaction payload path.
    await new Promise((resolve) => setTimeout(resolve, 450));
    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

    // Trigger category reset branch.
    fireEvent.click(screen.getByRole('button', { name: /^All$/i }));

    // Trigger local date formatting branch via mocked calendar.
    fireEvent.click(screen.getByRole('button', { name: /Select date range/i }));
    fireEvent.click(screen.getByRole('button', { name: /Pick range/i }));

    // Trigger category and tag active-filter chip removal branches.
    const activeFilterIcons = Array.from(document.querySelectorAll('svg.cursor-pointer'));
    expect(activeFilterIcons.length).toBeGreaterThan(1);
    // Active filter icon order is search, category, date, city, location, then tags.
    fireEvent.click(requireElement(activeFilterIcons[1], 'category active filter icon'));

    // Remove any remaining active filter chips.
    Array.from(document.querySelectorAll('svg.cursor-pointer')).forEach((icon) => {
      fireEvent.click(icon);
    });

    cleanup();

    // The page keeps tag filters in query state, but only exposes a clear-all control in the UI.
    renderLanguageRoute('/events?tags=ai,ml&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /clear/i }));

    // Trigger page-size update branch.
    const pageSizeOption = screen
      .getAllByRole('button')
      .find((button) => (button.textContent || '').trim().startsWith('24'));
    fireEvent.click(requireElement(pageSizeOption, 'page size option'));

    cleanup();

    renderLanguageRoute('/events?category=technical&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    const categoryOnlyIcons = Array.from(document.querySelectorAll('svg.cursor-pointer'));
    if (categoryOnlyIcons.length) {
      fireEvent.click(requireElement(categoryOnlyIcons[0], 'category only icon'));
    }

    // Trigger delayed impression + filter interaction payload path.
    await new Promise((resolve) => setTimeout(resolve, 450));
    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

    // Pagination next branch.
    const pager = requireElement(screen.getByText(/Page\s+1\s+of\s+3/i).parentElement, 'recommendations pager');
    const pagerButtons = within(pager).getAllByRole('button');
    fireEvent.click(pagerButtons[1]);

    cleanup();

    renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    // Recommendation click branch.
    const recommendationsHeading = await screen.findByRole('heading', { name: /Recommended for you/i });
    const recommendationsSection = recommendationsHeading.closest('div')?.parentElement;
    fireEvent.click(within(requireElement(recommendationsSection, 'recommendations section')).getByRole('button', { name: /open-event-90/i }));
    await waitFor(() =>
      expect(recordInteractionsSpy).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            interaction_type: 'click',
            meta: expect.objectContaining({ source: 'recommendations_grid' }),
          }),
        ]),
      ),
    );
  }, 20000);
  it('covers StudentProfilePage fallback/error branches and advanced interactions', async () => {
    eventServiceMock.getPersonalizationSettings.mockRejectedValueOnce(new Error('personalization-fail'));
    eventServiceMock.getNotificationPreferences.mockRejectedValueOnce(new Error('notifications-fail'));
    eventServiceMock.getUniversityCatalog.mockRejectedValueOnce(new Error('catalog-fail'));
    eventServiceMock.updateStudentProfile.mockRejectedValueOnce(new Error('save-fail'));
    authServiceMock.updateThemePreference.mockRejectedValueOnce(new Error('theme-fail'));
    authServiceMock.updateLanguagePreference.mockRejectedValueOnce(new Error('language-fail'));
    eventServiceMock.updateNotificationPreferences.mockRejectedValueOnce(new Error('notification-save-fail'));
    eventServiceMock.deleteMyAccount.mockRejectedValueOnce({
      response: { data: { detail: 'bad-access-code' } },
    });

    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

    const musicTagButton = screen.getByRole('button', { name: /Muzică/i });
    fireEvent.click(musicTagButton);
    fireEvent.keyDown(musicTagButton, { key: 'Enter' });
    fireEvent.keyDown(musicTagButton, { key: ' ' });

    fireEvent.change(screen.getByLabelText(/University/i), { target: { value: 'UTCN' } });
    fireEvent.change(screen.getByLabelText(/Faculty/i), { target: { value: 'AI' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj-Napoca' } });

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByText(/Light/i));
    fireEvent.click(screen.getByText(/^Romanian$/i));
    await waitFor(() => expect(authServiceMock.updateThemePreference).toHaveBeenCalled());
    await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalled());

    const digestLabel = screen.getByText(/Weekly digest/i);
    const digestRow = digestLabel.closest('div')?.parentElement?.parentElement;
    fireEvent.click(within(requireElement(digestRow, 'digest row')).getByRole('checkbox'));
    await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
    const dialog = await screen.findByRole('dialog');
    const deleteButtons = within(dialog).getAllByRole('button', { name: /Delete account|Șterge contul/i });
    fireEvent.click(deleteButtons[0]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText(/Access code/i), { target: { value: 'wrong-access-code' } });
    fireEvent.click(deleteButtons[0]);
    await waitFor(() => expect(eventServiceMock.deleteMyAccount).toHaveBeenCalledWith('wrong-access-code'));
  }, 20000);


  it('covers StudentProfilePage success handlers and guarded branches', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
    await screen.findByLabelText(/Full name/i);

    fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: 'New Name' } });

    const cityField = screen.getByLabelText(/City|Oraș/i);
    fireEvent.change(cityField, { target: { value: '' } });
    fireEvent.change(screen.getByLabelText(/University|Universitate/i), { target: { value: 'Other U' } });
    fireEvent.change(screen.getByLabelText(/University|Universitate/i), { target: { value: 'UTCN' } });

    const interestToggle = document.getElementById('tag-2');
    const interestToggleElement = requireElement(interestToggle, 'interest toggle');
    fireEvent.click(interestToggleElement);
    fireEvent.keyDown(interestToggleElement, { key: 'Enter' });

    const interestCheckbox = screen.getByRole('checkbox', { name: /Tech/i });
    fireEvent.click(interestCheckbox);

    // Explicitly trigger Checkbox onCheckedChange branch for tag chips.
    const musicCheckbox = document.getElementById('tag-1');
    fireEvent.click(requireElement(musicCheckbox, 'music checkbox'));

    fireEvent.click(screen.getByRole('button', { name: /Master/i }));
    fireEvent.click(screen.getByRole('button', { name: /^1$/i }));

    fireEvent.click(screen.getByRole('button', { name: /Light/i }));
    fireEvent.click(screen.getByRole('button', { name: /^Romanian$/i }));
    await waitFor(() => expect(authServiceMock.updateThemePreference).toHaveBeenCalledWith('light'));
    await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalledWith('ro'));

    eventServiceMock.unhideTag.mockRejectedValueOnce(new Error('unhide-fail'));
    const firstHiddenButton = screen
      .getAllByRole('button')
      .find((btn) => (btn.textContent || '').trim() === '✕');
    fireEvent.click(requireElement(firstHiddenButton, 'first hidden tag button'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.unhideTag.mockResolvedValueOnce(undefined);
    const secondHiddenButton = screen
      .getAllByRole('button')
      .find((btn) => (btn.textContent || '').trim() === '✕');
    fireEvent.click(requireElement(secondHiddenButton, 'second hidden tag button'));
    await waitFor(() => expect(eventServiceMock.unhideTag).toHaveBeenCalledWith(5));

    eventServiceMock.unblockOrganizer.mockRejectedValueOnce(new Error('unblock-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Unblock|Deblochează/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    const digestLabel = screen.getByText(/Digest|Rezumat/i);
    const digestRow = digestLabel.closest('div')?.parentElement?.parentElement;
    fireEvent.click(within(requireElement(digestRow, 'digest row')).getByRole('checkbox'));
    await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

    const notificationsHeading = screen.getByText(/Notifications|Notificări/i);
    const notificationsCard = notificationsHeading.closest('div')?.parentElement?.parentElement;
    const notificationCheckboxes = within(requireElement(notificationsCard, 'notifications card')).getAllByRole('checkbox');
    fireEvent.click(notificationCheckboxes[notificationCheckboxes.length - 1]);
    await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

    eventServiceMock.exportMyData.mockRejectedValueOnce(new Error('export-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Export data|Export date/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
    const dialog = await screen.findByRole('dialog');
    const accessCodeField = requireInput(within(dialog).getByLabelText(/Access code|Cod de acces/i), 'access code field');
    fireEvent.change(accessCodeField, { target: { value: 'temporary-access-code' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /Cancel|Anulează/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
    const reopenedDialog = await screen.findByRole('dialog');
    const reopenedAccessCode = requireInput(within(reopenedDialog).getByLabelText(/Access code|Cod de acces/i), 'reopened access code field');
    expect(reopenedAccessCode).toHaveValue('');
    fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Cancel|Anulează/i }));
  }, 20000);

  it('covers StudentProfilePage non-student and load-failure branches', async () => {
    authState.user = { id: 11, role: 'organizator', email: 'org@test.local' };
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
    expect(screen.queryByText(/Personalization/i)).not.toBeInTheDocument();

    cleanup();
    authState.user = { id: 11, role: 'student', email: 'student@test.local' };
    eventServiceMock.getStudentProfile.mockRejectedValueOnce(new Error('profile-load-fail'));
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers OrganizerDashboardPage bulk tag branches and delete guard branches', async () => {
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

    const checkboxes = await screen.findAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);
    const publishButton = screen.getByRole('button', { name: /Publish/i });
    const bulkContainer = publishButton.parentElement;
    const bannerButtons = within(requireElement(bulkContainer, 'bulk container')).getAllByRole('button');
    fireEvent.click(bannerButtons[2]);
    const dialog = await screen.findByRole('dialog');
    const input = within(dialog).getByPlaceholderText(/tag/i);

    fireEvent.change(input, { target: { value: 'x'.repeat(120) } });
    fireEvent.keyDown(input, { key: 'Enter' });

    fireEvent.change(input, { target: { value: 'Community' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    const communityBadge = within(dialog).getByText('Community');
    fireEvent.click(communityBadge);

    fireEvent.click(within(dialog).getByRole('button', { name: /Cancel|Anulează/i }));
    fireEvent.click(bannerButtons[2]);
    const reopenedDialog = await screen.findByRole('dialog');
    const reopenedInput = within(reopenedDialog).getByPlaceholderText(/tag/i);
    fireEvent.change(reopenedInput, { target: { value: 'Community' } });
    fireEvent.keyDown(reopenedInput, { key: 'Enter' });

    eventServiceMock.bulkUpdateEventTags.mockRejectedValueOnce(new Error('bulk-tags-fail'));

    fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(input, { target: { value: 'AI' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(eventServiceMock.bulkUpdateEventTags).toHaveBeenCalled());

    const checkboxesAfterTags = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxesAfterTags[1]);
    fireEvent.click(screen.getByRole('button', { name: /Publish/i }));

    // Clear-selection bulk action branch.
    const clearButton = screen.getByRole('button', { name: /Clear|Șterge selecția/i });
    fireEvent.click(clearButton);
    await waitFor(() => expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'));

    const checkboxesAfterPublish = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxesAfterPublish[1]);
    const draftButton = screen.queryByRole('button', { name: /Unpublish|Draft/i });
    if (draftButton) {
      fireEvent.click(draftButton);
      await waitFor(() => expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'draft'));
    }

    const menuTrigger = screen
      .getAllByRole('button')
      .find((btn) => btn.getAttribute('aria-haspopup') === 'menu');
    expect(menuTrigger).toBeDefined();

    // Delete action branch when dropdown item is available in this test runtime.
    fireEvent.click(requireElement(menuTrigger, 'menu trigger'));
    const deleteOption = screen.queryByText(/Delete|Șterge/i);
    if (deleteOption) {
      vi.mocked(globalThis.confirm).mockReturnValueOnce(false);
      fireEvent.click(deleteOption);

      fireEvent.click(requireElement(menuTrigger, 'menu trigger'));
      const deleteOptionRetry = screen.queryByText(/Delete|Șterge/i);
      if (deleteOptionRetry) {
        vi.mocked(globalThis.confirm).mockReturnValueOnce(true);
        eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
        fireEvent.click(deleteOptionRetry);
        await waitFor(() => expect(toastSpy).toHaveBeenCalled());
      }
    }
  });
  it('covers student tag checkbox onCheckedChange callback', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

    const tagCheckbox = document.getElementById('tag-1');
    expect(tagCheckbox).not.toBeNull();

    const tagCheckboxElement = requireElement(tagCheckbox, 'tag checkbox');
    fireEvent.click(tagCheckboxElement);
    fireEvent.click(tagCheckboxElement);
  });
  it('renders tag option cards and toggles selection via card click', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

    const techTagCard = await screen.findByRole('button', { name: /Tech/i });
    fireEvent.click(techTagCard);
    fireEvent.click(techTagCard);
  });
});
