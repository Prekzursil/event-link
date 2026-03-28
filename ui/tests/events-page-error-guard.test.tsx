import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventsPage,
  getEventPagesFixtures,
  makeEvent,
} from './events-form-and-events-page.shared';

const { authState, eventServiceMock, toastSpy } = getEventPagesFixtures();

it('covers the error state and unauthenticated favorite guard', async () => {
  eventServiceMock.getEvents.mockRejectedValueOnce(new Error('load-events-failed'));
  renderLanguageRoute('/events', '/events', <EventsPage />);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  cleanup();
  authState.isAuthenticated = false;
  authState.user = null;
  eventServiceMock.getEvents.mockResolvedValueOnce({
    items: [makeEvent(10)],
    total: 1,
    page: 1,
    page_size: 12,
    total_pages: 1,
  });
  renderLanguageRoute('/events', '/events', <EventsPage />);
  await screen.findByText(/Event 10/i);
  fireEvent.click(screen.getByText('favorite-10'));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
});
