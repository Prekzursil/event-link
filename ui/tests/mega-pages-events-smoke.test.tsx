import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventDetailPage,
  EventsPage,
  getMegaPagesSmokeFixtures,
} from './mega-pages-smoke.shared';

const { eventServiceMock, navigateSpy, toastSpy } = getMegaPagesSmokeFixtures();

describe('mega pages events smoke', () => {
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
});
