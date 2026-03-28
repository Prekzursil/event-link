import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  EventsPage,
  getEventPagesFixtures,
  makeEvent,
} from './events-form-and-events-page.shared';
import { renderLanguageRoute } from './page-test-helpers';

const { eventServiceMock, recordInteractionsSpy } = getEventPagesFixtures();

it('covers no-results clear-all behavior', async () => {
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
});

it('covers filter tracking for pre-filled event filters', async () => {
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
