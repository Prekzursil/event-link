import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';

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

vi.mock('@/components/ui/select', async () => {
  const ReactMod = await vi.importActual<typeof import('react')>('react');
  type SelectCtx = { onValueChange?: (value: string) => void; disabled?: boolean };
  const SelectContext = ReactMod.createContext<SelectCtx>({});

  const Select = ({ children, onValueChange, disabled }: { children: React.ReactNode; onValueChange?: (value: string) => void; disabled?: boolean }) => (
    <SelectContext.Provider value={{ onValueChange, disabled }}>{children}</SelectContext.Provider>
  );
  const SelectTrigger = ({ children, ...props }: React.ComponentProps<'button'>) => (
    <button type="button" {...props}>
      {children}
    </button>
  );
  const SelectValue = ({ placeholder }: { placeholder?: string }) => <span>{placeholder ?? 'value'}</span>;
  const SelectContent = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
  const SelectItem = ({ value, children }: { value: string; children: React.ReactNode }) => {
    const ctx = ReactMod.useContext(SelectContext);
    return (
      <button type="button" disabled={ctx.disabled} onClick={() => ctx.onValueChange?.(value)}>
        {children}
      </button>
    );
  };
  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
});

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
  localStorage.setItem('language_preference', 'en');

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: true,
      media: '(min-width: 640px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });

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
    renderRoute('/events?sort=time', '/events', <EventsPage />);

    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    await waitFor(() => expect(eventServiceMock.getFavorites).toHaveBeenCalled());

    expect(await screen.findByText(/Recommended 90/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText('favorite-1'));
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByText('open-1'));
    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 12, total_pages: 1 });
    renderRoute('/events?search=abc', '/events', <EventsPage />);
    expect(await screen.findByText(/No events found/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Clear all/i }));

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [makeEvent(11)], total: 1, page: 1, page_size: 12, total_pages: 1 });
    renderRoute('/events?category=Technical&sort=time', '/events', <EventsPage />);
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
    renderRoute('/events', '/events', <EventsPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    authState.isAuthenticated = false;
    authState.user = null;
    eventServiceMock.getEvents.mockResolvedValueOnce({ items: [makeEvent(10)], total: 1, page: 1, page_size: 12, total_pages: 1 });
    renderRoute('/events', '/events', <EventsPage />);
    await screen.findByText(/Event 10/i);
    fireEvent.click(screen.getByText('favorite-10'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers EventFormPage create flow with suggest/apply and validation branches', async () => {
    renderRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    const form = screen.getByRole('button', { name: /Create event/i }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'AI Meetup' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'A meetup about AI' } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '100' } });

    fireEvent.click(screen.getByRole('button', { name: /Create event/i }));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/events/77');
  });

  it('covers EventFormPage edit load/update success and load failure redirect', async () => {
    renderRoute('/organizer/events/33/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(33));

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateEvent).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');

    cleanup();
    eventServiceMock.getEvent.mockRejectedValueOnce(new Error('load-failed'));
    renderRoute('/organizer/events/88/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/organizer'));
  });

  it('covers EventFormPage validation branches, suggest-error detail, and tag/image helpers', async () => {
    renderRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Validation Event' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'Validation description' } });

    const submit = screen.getByRole('button', { name: /Create event/i });
    const form = submit.closest('form') as HTMLFormElement;

    // Category required branch before suggestion fills it.
    fireEvent.submit(form);
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
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));

    // Explicitly exercise select handlers for category + status.
    screen.getAllByRole('button', { name: /Technical|Tehnic/i }).forEach((button) => fireEvent.click(button));
    screen.getAllByRole('button', { name: /Draft|Ciornă/i }).forEach((button) => fireEvent.click(button));

    fireEvent.submit(form);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: '' } });
    fireEvent.submit(form);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.submit(form);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Start date/i), { target: { value: '2026-03-10T10:00' } });
    fireEvent.change(screen.getByLabelText(/End date/i), { target: { value: '2026-03-10T12:00' } });
    fireEvent.submit(form);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '20' } });

    const coverInput = document.getElementById('cover_url') as HTMLInputElement;
    expect(coverInput).not.toBeNull();
    fireEvent.change(coverInput, { target: { value: 'https://example.com/img.jpg' } });
    const preview = screen.getByAltText(/Preview/i) as HTMLImageElement;
    fireEvent.error(preview);
    expect(preview.style.display).toBe('none');

    const addTagButton = screen.getByRole('button', { name: /Add/i });
    const tagInput = screen.getByPlaceholderText(/tag/i) as HTMLInputElement;
    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(addTagButton);
    expect(screen.getByText('AI')).toBeInTheDocument();

    const removeIcon = document.querySelector('svg.h-3.w-3.cursor-pointer');
    expect(removeIcon).not.toBeNull();
    fireEvent.click(removeIcon as SVGElement);

    eventServiceMock.createEvent.mockRejectedValueOnce({ response: { data: { detail: 'create-fail' } } });
    fireEvent.submit(form);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    // Enter key path in tag input should also add tags.
    fireEvent.change(tagInput, { target: { value: 'ML' } });
    fireEvent.keyDown(tagInput, { key: 'Enter' });

    fireEvent.submit(form);
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
  }, 20000);

  it('covers EventFormPage back and cancel navigation actions', async () => {
    renderRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    expect(navigateSpy).toHaveBeenCalledWith(-1);

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');
  });
});










