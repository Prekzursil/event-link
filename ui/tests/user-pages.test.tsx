import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';

const { eventServiceMock, authState, toastSpy } = vi.hoisted(() => ({
  eventServiceMock: {
    getFavorites: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    getMyEvents: vi.fn(),
    getOrganizerEvents: vi.fn(),
    getMyCalendar: vi.fn(),
  },
  authState: {
    isOrganizer: false,
  },
  toastSpy: vi.fn(),
}));

vi.mock('@/services/event.service', () => ({
  default: eventServiceMock,
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock('@/components/events/EventCard', () => ({
  EventCard: ({ event, onFavoriteToggle, isFavorite, showEditButton }: { event: { id: number; title: string }; onFavoriteToggle?: (eventId: number, shouldFavorite: boolean) => void; isFavorite?: boolean; showEditButton?: boolean }) => (
    <div data-testid={`event-${event.id}`}>
      <span>{event.title}</span>
      <button onClick={() => onFavoriteToggle?.(event.id, !isFavorite)}>toggle-{event.id}</button>
      <button onClick={() => onFavoriteToggle?.(event.id, true)}>favorite-on-{event.id}</button>
      {showEditButton ? <span>edit-mode</span> : null}
    </div>
  ),
}));

vi.mock('@/components/ui/loading', () => ({
  LoadingPage: ({ message }: { message?: string }) => <div>{message ?? 'loading'}</div>,
  LoadingSpinner: () => <span>spinner</span>,
}));

import { FavoritesPage } from '@/pages/FavoritesPage';
import { MyEventsPage } from '@/pages/MyEventsPage';

function renderWithProviders(node: React.ReactNode, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LanguageProvider>
        <Routes>
          <Route path="*" element={node} />
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

function makeEvent(id: number, startOffsetDays: number) {
  const start = new Date();
  start.setDate(start.getDate() + startOffsetDays);
  return {
    id,
    title: `Event ${id}`,
    description: 'desc',
    category: 'Edu',
    start_time: start.toISOString(),
    city: 'Cluj',
    location: 'Hall',
    max_seats: 20,
    seats_taken: 1,
    tags: [],
  };
}

describe('favorites and my-events pages', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.setItem('language_preference', 'en');
    authState.isOrganizer = false;
    eventServiceMock.getFavorites.mockResolvedValue({ items: [] });
    eventServiceMock.addToFavorites.mockResolvedValue(undefined);
    eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
    eventServiceMock.getMyEvents.mockResolvedValue([]);
    eventServiceMock.getOrganizerEvents.mockResolvedValue([]);
    eventServiceMock.getMyCalendar.mockResolvedValue('BEGIN:VCALENDAR');
  });

  it('covers FavoritesPage empty, populated, and toggle error paths', async () => {
    renderWithProviders(<FavoritesPage />, '/favorites');
    expect(await screen.findByText(/No favorite events/i)).toBeInTheDocument();

    cleanup();
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [makeEvent(1, 5)] });
    renderWithProviders(<FavoritesPage />, '/favorites');
    expect(await screen.findByTestId('event-1')).toBeInTheDocument();

    fireEvent.click(screen.getByText('favorite-on-1'));
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByText('toggle-1'));
    await waitFor(() => expect(eventServiceMock.removeFromFavorites).toHaveBeenCalledWith(1));

    cleanup();
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [makeEvent(2, 5)] });
    eventServiceMock.removeFromFavorites.mockRejectedValueOnce(new Error('fail'));
    renderWithProviders(<FavoritesPage />, '/favorites');
    expect(await screen.findByTestId('event-2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('toggle-2'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getFavorites.mockRejectedValueOnce(new Error('favorites-load-fail'));
    renderWithProviders(<FavoritesPage />, '/favorites');
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers MyEventsPage student and organizer branches + calendar download outcomes', async () => {
    const upcoming = makeEvent(3, 3);
    const upcomingLater = makeEvent(6, 9);
    const past = makeEvent(4, -2);
    const pastOlder = makeEvent(7, -6);

    eventServiceMock.getMyEvents.mockResolvedValueOnce([upcomingLater, pastOlder, upcoming, past]);
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [upcoming] });

    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob://x');
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const appendSpy = vi.spyOn(document.body, 'appendChild');

    renderWithProviders(<MyEventsPage />, '/my-events');

    expect(await screen.findByText(/Upcoming/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText('toggle-3'));
    await waitFor(() => expect(eventServiceMock.removeFromFavorites).toHaveBeenCalledWith(3));
    fireEvent.click(screen.getByText('toggle-6'));
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(6));
    fireEvent.click(screen.getByRole('button', { name: /Calendar \(\.ics\)/i }));
    await waitFor(() => expect(eventServiceMock.getMyCalendar).toHaveBeenCalled());
    expect(createObjectURLSpy).toHaveBeenCalled();
    expect(revokeObjectURLSpy).toHaveBeenCalled();
    expect(appendSpy).toHaveBeenCalled();

    cleanup();
    authState.isOrganizer = true;
    eventServiceMock.getMyEvents.mockResolvedValueOnce([upcoming]);
    eventServiceMock.getOrganizerEvents.mockResolvedValueOnce([makeEvent(5, 2), makeEvent(8, 6)]);
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [] });
    renderWithProviders(<MyEventsPage />, '/my-events');

    expect(await screen.findByText(/Created by me/i)).toBeInTheDocument();
    expect(screen.getByTestId('event-5')).toBeInTheDocument();
    expect(screen.getAllByText('edit-mode').length).toBeGreaterThan(0);

    cleanup();
    eventServiceMock.getMyEvents.mockResolvedValueOnce([upcoming]);
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [] });
    eventServiceMock.getMyCalendar.mockRejectedValueOnce(new Error('download-fail'));
    eventServiceMock.addToFavorites.mockRejectedValueOnce(new Error('favorites-fail'));
    authState.isOrganizer = false;
    renderWithProviders(<MyEventsPage />, '/my-events');
    await screen.findByText(/Upcoming/i);
    fireEvent.click(screen.getByText('toggle-3'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Calendar \(\.ics\)/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getMyEvents.mockRejectedValueOnce(new Error('my-events-load-fail'));
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [] });
    renderWithProviders(<MyEventsPage />, '/my-events');
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers MyEventsPage empty organizer and upcoming states', async () => {
    authState.isOrganizer = true;
    eventServiceMock.getMyEvents.mockResolvedValueOnce([makeEvent(9, -1)]);
    eventServiceMock.getOrganizerEvents.mockResolvedValueOnce([]);
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [] });

    renderWithProviders(<MyEventsPage />, '/my-events');

    expect(await screen.findByText(/You haven't created any events/i)).toBeInTheDocument();
    expect(screen.getByText(/Create event/i)).toBeInTheDocument();

    cleanup();
    authState.isOrganizer = false;
    eventServiceMock.getMyEvents.mockResolvedValueOnce([makeEvent(10, -2)]);
    eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [] });

    renderWithProviders(<MyEventsPage />, '/my-events');
    expect(await screen.findByText(/No upcoming events/i)).toBeInTheDocument();
  });
});
