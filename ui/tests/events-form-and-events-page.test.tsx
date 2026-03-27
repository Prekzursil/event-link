import React from 'react';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { defineMutableValue, renderLanguageRoute, requireElement, setEnglishPreference } from './page-test-helpers';

const {
  toastSpy,
  navigateSpy,
  recordInteractionsSpy,
  eventServiceMock,
  authState,
} = vi.hoisted(() => ({
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
  EventCard: ({ event, onFavoriteToggle, onEventClick, isFavorite }: {
    event: { id: number; title: string };
    onFavoriteToggle?: (eventId: number, shouldFavorite: boolean) => void;
    onEventClick?: (eventId: number) => void;
    isFavorite?: boolean;
  }) => (
    <div data-testid={`mock-event-card-${event.id}`}>
      <span>{event.title}</span>
      <button onClick={() => onFavoriteToggle?.(event.id, !isFavorite)}>{`favorite-${event.id}`}</button>
      <button onClick={() => onEventClick?.(event.id)}>{`open-${event.id}`}</button>
    </div>
  ),
}));

import { EventsPage } from '@/pages/events/EventsPage';
import { EventFormPage } from '@/pages/organizer/EventFormPage';

function requireForm(buttonName: RegExp): HTMLFormElement {
  const form = screen.getByRole('button', { name: buttonName }).closest('form');
  if (!(form instanceof HTMLFormElement)) {
    throw new TypeError(`Expected a form for ${buttonName.toString()}`);
  }
  return form;
}

function makeEvent(id: number, title = `Event ${id}`) {
  return {
    id,
    title,
    description: 'desc',
    category: 'Technical',
    start_time: new Date(Date.now() + 3600000).toISOString(),
    end_time: new Date(Date.now() + 7200000).toISOString(),
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

  eventServiceMock.getEvents.mockImplementation(async (filters: { sort?: string; page_size?: number }) => {
    if (filters?.sort === 'recommended' && filters?.page_size === 4) {
      return { items: [makeEvent(90, 'Recommended 90')], total: 1, page: 1, page_size: 4, total_pages: 1 };
    }
    return { items: [makeEvent(1)], total: 1, page: 1, page_size: 12, total_pages: 1 };
  });
  eventServiceMock.getFavorites.mockResolvedValue({ items: [makeEvent(90, 'Recommended 90')] });
  eventServiceMock.addToFavorites.mockResolvedValue(undefined);
  eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);

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

describe('events page and event form branch coverage', () => {
  it('covers EventsPage recommendations, favorites, interactions and no-results branch', async () => {
    renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);

    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    await waitFor(() => expect(eventServiceMock.getFavorites).toHaveBeenCalled());

    expect(await screen.findByText(/Recommended 90/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('favorite-1'));
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByText('open-1'));
    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 12, total_pages: 1 });
    renderLanguageRoute('/events?search=abc', '/events', <EventsPage />);
    expect(await screen.findByText(/No events found/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Clear all/i }));

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [makeEvent(11)], total: 1, page: 1, page_size: 12, total_pages: 1 });
    renderLanguageRoute('/events?category=Technical&sort=time', '/events', <EventsPage />);
    await screen.findByText(/Event 11/i);
    await waitFor(() => {
      const hasFilterPayload = recordInteractionsSpy.mock.calls.some(([payload]) =>
        Array.isArray(payload) && payload.some((item: { interaction_type?: string }) => item?.interaction_type === 'filter'),
      );
      expect(hasFilterPayload).toBe(true);
    });
  });

  it('covers EventsPage error and unauthenticated favorite guard', async () => {
    eventServiceMock.getEvents.mockRejectedValueOnce(new Error('load-events-failed'));
    renderLanguageRoute('/events', '/events', <EventsPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    authState.isAuthenticated = false;
    authState.user = null;
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [makeEvent(10)], total: 1, page: 1, page_size: 12, total_pages: 1 });
    renderLanguageRoute('/events', '/events', <EventsPage />);
    await screen.findByText(/Event 10/i);
    fireEvent.click(screen.getByText('favorite-10'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers EventsPage media fallbacks, delayed cleanup, and blank interaction metadata branches', async () => {
    defineMutableValue(globalThis, 'matchMedia', undefined);

    let rejectLateRequest: ((error: Error) => void) | undefined;
    eventServiceMock.getEvents.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectLateRequest = reject as (error: Error) => void;
      }),
    );
    const pendingRender = renderLanguageRoute('/events?search=late', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    pendingRender.unmount();
    rejectLateRequest?.(new Error('late-fail'));
    await Promise.resolve();
    expect(toastSpy).not.toHaveBeenCalled();

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(30, 'Search only event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?search=solo&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(
      recordInteractionsSpy.mock.calls.some(([payload]) =>
        Array.isArray(payload) &&
        payload.some(
          (item: {
            interaction_type?: string;
            meta?: { category?: string; city?: string; location?: string };
          }) =>
            item?.interaction_type === 'search' &&
            item.meta?.category === undefined &&
            item.meta?.city === undefined &&
            item.meta?.location === undefined,
        ),
      ),
    ).toBe(true);

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(31, 'City filtered event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?city=Cluj&page=1&category=Technical', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    screen.getAllByRole('button', { name: /^All$/i }).forEach((button) => fireEvent.click(button));
    await waitFor(() =>
      expect(eventServiceMock.getEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: '' }),
      ),
    );
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(
      recordInteractionsSpy.mock.calls.some(([payload]) =>
        Array.isArray(payload) &&
        payload.some(
          (item: {
            interaction_type?: string;
            meta?: { category?: string; city?: string; location?: string };
          }) =>
            item?.interaction_type === 'filter' &&
            item.meta?.category === undefined &&
            item.meta?.city === 'Cluj' &&
            item.meta?.location === undefined,
        ),
      ),
    ).toBe(true);

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(31, 'Category selected event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);
    await waitFor(() =>
      expect(eventServiceMock.getEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: 'Technical' }),
      ),
    );

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(32, 'Date filtered event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?start_date=2026-03-10&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    expect(screen.getByText(/10 Mar 2026/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /10 Mar 2026/i }));
    fireEvent.click(requireElement(screen.queryByRole('button', { name: /Clear range/i }), 'clear range button'));
  }, 20000);

  it('covers EventFormPage create flow with suggest/apply and validation branches', async () => {
    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'AI Meetup' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'A meetup about AI' } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());

    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '100' } });

    fireEvent.click(screen.getByRole('button', { name: /Create event/i }));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/events/77');
  });

  it('covers EventFormPage edit load/update success and load failure redirect', async () => {
    renderLanguageRoute('/organizer/events/33/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(33));

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateEvent).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');

    cleanup();
    eventServiceMock.getEvent.mockRejectedValueOnce(new Error('load-failed'));
    renderLanguageRoute('/organizer/events/88/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/organizer'));
  });

  it('covers EventFormPage validation branches, suggest-error detail, and tag/image helpers', async () => {
    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Validation Event' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'Validation description' } });

    // Category required branch before suggestion fills it.
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.suggestEvent.mockRejectedValueOnce({ response: { data: { detail: 'bad-suggest' } } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.suggestEvent.mockResolvedValueOnce({
      suggested_category: 'Technical',
      suggested_city: 'Cluj',
      suggested_tags: ['A'],
      duplicates: [],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));

    // Explicitly exercise select handlers for category + status.
    screen.getAllByRole('button', { name: /Technical|Tehnic/i }).forEach((button) => fireEvent.click(button));
    screen.getAllByRole('button', { name: /Draft|Ciornă/i }).forEach((button) => fireEvent.click(button));

    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: '' } });
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.change(screen.getByLabelText(/End date/i), { target: { value: '2026-03-10T12:00' } });
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '20' } });

    const coverInput = document.getElementById('cover_url');
    expect(coverInput).not.toBeNull();
    fireEvent.change(coverInput, { target: { value: 'https://example.com/img.jpg' } });
    const preview = screen.getByAltText(/Preview/i);
    fireEvent.error(preview);
    expect(preview.style.display).toBe('none');

    const addTagButton = screen.getByRole('button', { name: /Add/i });
    const tagInput = screen.getByPlaceholderText(/tag/i);
    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(addTagButton);
    expect(screen.getByText('AI')).toBeInTheDocument();

    const removeIcon = document.querySelector('svg.h-3.w-3.cursor-pointer');
    expect(removeIcon).not.toBeNull();
    fireEvent.click(removeIcon!);

    eventServiceMock.createEvent.mockRejectedValueOnce({ response: { data: { detail: 'create-fail' } } });
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    // Enter key path in tag input should also add tags.
    fireEvent.change(tagInput, { target: { value: 'ML' } });
    fireEvent.keyDown(tagInput, { key: 'Enter' });

    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
  }, 20000);

  it('covers EventFormPage back and cancel navigation actions', async () => {
    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    expect(navigateSpy).toHaveBeenCalledWith(-1);

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');
  });

  it('covers EventFormPage sparse edit defaults and suggestion fallback rendering', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce({
      ...makeEvent(44, 'Sparse event'),
      description: undefined,
      category: undefined,
      end_time: undefined,
      city: undefined,
      location: undefined,
      max_seats: undefined,
      cover_url: undefined,
      status: undefined,
      tags: [],
    });

    renderLanguageRoute('/organizer/events/44/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(44));
    expect(screen.getByLabelText(/Description/i)).toHaveValue('');
    expect(screen.getByLabelText(/City/i)).toHaveValue('');
    expect(screen.getByLabelText(/Location/i)).toHaveValue('');
    expect(screen.getByLabelText(/Max seats/i)).toHaveValue(null);

    cleanup();
    eventServiceMock.suggestEvent.mockResolvedValueOnce({
      suggested_category: '',
      suggested_city: '',
      suggested_tags: [],
      duplicates: [
        {
          id: 201,
          title: 'Possible duplicate',
          start_time: new Date().toISOString(),
          city: '',
          similarity: 0.33,
        },
      ],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);
    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Fallback event' } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());
    expect(screen.getAllByText('—').length).toBeGreaterThan(1);
    expect(screen.getByText(/- • 33%/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));
    expect(screen.getByLabelText(/City/i)).toHaveValue('');

    const tagInput = screen.getByPlaceholderText(/tag/i);
    fireEvent.keyDown(tagInput, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/i }));
    expect(screen.queryByText(/^AI$/i)).not.toBeInTheDocument();

    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/i }));
    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/i }));
    expect(screen.getAllByText('AI')).toHaveLength(1);

    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '' } });
    expect(screen.getByLabelText(/Max seats/i)).toHaveValue(null);
  });

  it('covers EventFormPage suggest payload timestamps, duplicate-apply retention, and max-seats reset', async () => {
    let resolveSuggestion: ((value: Awaited<ReturnType<typeof eventServiceMock.suggestEvent>>) => void) | undefined;
    eventServiceMock.suggestEvent.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSuggestion = resolve as (value: Awaited<ReturnType<typeof eventServiceMock.suggestEvent>>) => void;
      }),
    );

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Suggest payload event' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Braila' } });
    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);

    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() =>
      expect(eventServiceMock.suggestEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Suggest payload event',
          city: 'Braila',
          start_time: new Date('2026-03-10T10:00').toISOString(),
        }),
      ),
    );

    resolveSuggestion?.({
      suggested_category: 'Social',
      suggested_city: 'Iasi',
      suggested_tags: ['AI'],
      duplicates: [],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));

    expect(screen.getByLabelText(/City/i)).toHaveValue('Braila');
    expect(screen.getAllByText('AI').length).toBeGreaterThan(0);

    const maxSeatsInput = screen.getByLabelText(/Max seats/i);
    fireEvent.change(maxSeatsInput, { target: { value: '12' } });
    fireEvent.change(maxSeatsInput, { target: { value: '' } });
    expect(maxSeatsInput).toHaveValue(null);

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Hall A' } });
    fireEvent.change(maxSeatsInput, { target: { value: '24' } });
    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() =>
      expect(eventServiceMock.createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          category: 'Technical',
          city: 'Braila',
          max_seats: 24,
        }),
      ),
    );
  }, 20000);

  it('covers EventFormPage generic suggestion and submit fallback errors', async () => {
    eventServiceMock.suggestEvent.mockRejectedValueOnce(new Error('plain-suggest-error'));
    eventServiceMock.createEvent.mockRejectedValueOnce(new Error('plain-create-error'));

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Fallback create event' } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() =>
      expect(eventServiceMock.suggestEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Fallback create event',
          description: undefined,
          city: undefined,
          location: undefined,
          start_time: undefined,
        }),
      ),
    );
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);
    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '25' } });

    fireEvent.submit(requireForm(/Create event/i));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });
});
