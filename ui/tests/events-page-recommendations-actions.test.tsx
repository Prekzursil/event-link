import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  EventsPage,
  getEventPagesFixtures,
  makeEvent,
} from './events-form-and-events-page.shared';
import { renderLanguageRoute } from './page-test-helpers';

const { eventServiceMock, recordInteractionsSpy } = getEventPagesFixtures();

it('covers recommendations, favorites, and click tracking', async () => {
  renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
  await waitFor(() => expect(eventServiceMock.getFavorites).toHaveBeenCalled());
  expect(await screen.findByText(/Recommended 90/i)).toBeInTheDocument();

  fireEvent.click(screen.getByText('favorite-1'));
  await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));
  fireEvent.click(screen.getByText('favorite-1'));
  await waitFor(() => expect(eventServiceMock.removeFromFavorites).toHaveBeenCalledWith(1));
  fireEvent.click(screen.getByText('open-1'));
  await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());
});

it('covers click tracking failure fallback', async () => {
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
      expect.objectContaining({ interaction_type: 'click', event_id: 12 }),
    ]),
  );
});
