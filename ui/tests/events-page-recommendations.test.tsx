import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventsPage,
  getEventPagesFixtures,
  makeEvent,
} from './events-form-and-events-page.shared';

const { eventServiceMock, recordInteractionsSpy } = getEventPagesFixtures();

it('covers recommendations, favorites, click tracking, no-results, and filter tracking', async () => {
  renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);

  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
  await waitFor(() => expect(eventServiceMock.getFavorites).toHaveBeenCalled());

  expect(await screen.findByText(/Recommended 90/i)).toBeInTheDocument();

  fireEvent.click(screen.getByText('favorite-1'));
  await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));

  fireEvent.click(screen.getByText('open-1'));
  await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

  cleanup();
  recordInteractionsSpy.mockReturnValueOnce({
    catch: (handler: (error: Error) => void) => {
      handler(new Error('click-fail'));
      return Promise.resolve(undefined);
    },
  });
  eventServiceMock.getEvents.mockResolvedValueOnce({
    items: [makeEvent(12)],
    total: 1,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);
  await screen.findByText(/Event 12/i);
  fireEvent.click(screen.getByText('open-12'));
  await waitFor(() =>
    expect(recordInteractionsSpy).toHaveBeenCalledWith([
      expect.objectContaining({
        interaction_type: 'click',
        event_id: 12,
      }),
    ]),
  );

  cleanup();
  eventServiceMock.getEvents.mockResolvedValueOnce({
    items: [],
    total: 0,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  renderLanguageRoute('/events?search=abc', '/events', <EventsPage />);
  expect(await screen.findByText(/No events found/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Clear all/i }));

  cleanup();
  eventServiceMock.getEvents.mockResolvedValueOnce({
    items: [makeEvent(11)],
    total: 1,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  renderLanguageRoute('/events?category=Technical&sort=time', '/events', <EventsPage />);
  await screen.findByText(/Event 11/i);
  await waitFor(() => {
    const hasFilterPayload = recordInteractionsSpy.mock.calls.some(([payload]) =>
      Array.isArray(payload) &&
      payload.some((item: { interaction_type?: string }) => item?.interaction_type === 'filter'),
    );
    expect(hasFilterPayload).toBe(true);
  });
});
