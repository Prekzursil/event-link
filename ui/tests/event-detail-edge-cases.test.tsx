import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import { EventDetailPage, getEventDetailFixtures } from './event-detail-branches.shared';

const { eventServiceMock, toastSpy } = getEventDetailFixtures();

function renderEventDetail(path = '/events/1') {
  return renderLanguageRoute(path, '/events/:id', <EventDetailPage />);
}

function makeEvent(overrides?: Partial<Record<string, unknown>>) {
  return {
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
    ...overrides,
  };
}

describe('event detail edge cases', () => {
  it('covers the eventless route, fallback errors, and ended/full display branches', async () => {
    renderLanguageRoute('/events', '/events', <EventDetailPage />);
    expect(eventServiceMock.getEvent).not.toHaveBeenCalled();

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        available_seats: undefined,
        end_time: undefined,
        owner_name: '',
      }),
    );
    eventServiceMock.registerForEvent.mockRejectedValueOnce(new Error('plain-register-fail'));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    expect(screen.getAllByText(/^Organizer$/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        is_registered: true,
        available_seats: undefined,
      }),
    );
    eventServiceMock.unregisterFromEvent.mockRejectedValueOnce(new Error('plain-unregister-fail'));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: /Unregister/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        available_seats: 0,
        owner_name: '',
      }),
    );
    renderEventDetail('/events/1');
    await waitFor(() => expect(screen.getByText(/Full/i)).toBeInTheDocument());

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        start_time: new Date(Date.now() - 3_600_000).toISOString(),
        available_seats: 0,
      }),
    );
    renderEventDetail('/events/1');
    await waitFor(() => expect(screen.getByText(/^Ended$/i)).toBeInTheDocument());
    expect(screen.getByText(/This event has ended/i)).toBeInTheDocument();

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(makeEvent({ city: '', location: '' }));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    expect(screen.queryByText(/Location/i)).not.toBeInTheDocument();

    cleanup();
    eventServiceMock.getEvent.mockResolvedValueOnce(makeEvent({ tags: [{ id: 7, name: 'AI' }] }));
    eventServiceMock.hideTag.mockRejectedValueOnce(new Error('plain-hide-fail'));
    eventServiceMock.blockOrganizer.mockRejectedValueOnce(new Error('plain-block-fail'));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: /AI/i }));
    fireEvent.click(screen.getByRole('button', { name: /Hide|Ascunde/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Block organizer|Blochează organizator/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);
});
