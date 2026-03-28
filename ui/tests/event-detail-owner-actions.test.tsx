import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { getEventDetailFixtures } from './event-detail-branches.shared';
import {
  makeEvent,
  renderEventDetail,
} from './event-detail-owner-preferences.shared';

const { eventServiceMock, navigateSpy, toastSpy } = getEventDetailFixtures();

it('covers owner clone success and error branches', async () => {
  eventServiceMock.getEvent.mockResolvedValueOnce(
    makeEvent({ is_owner: true, is_registered: false }),
  );
  renderEventDetail('/events/1');
  await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

  fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
  await waitFor(() => expect(eventServiceMock.cloneEvent).toHaveBeenCalledWith(1));
  expect(navigateSpy).toHaveBeenCalledWith('/organizer/events/77/edit');

  eventServiceMock.cloneEvent.mockRejectedValueOnce(new Error('clone-failed'));
  fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 20000);

it('covers register error rollback, back navigation, and the cover fallback image', async () => {
  eventServiceMock.getEvent.mockResolvedValueOnce(
    makeEvent({
      cover_url: 'https://example.com/broken.jpg',
      description: '',
      status: 'draft',
      max_seats: 10,
      available_seats: 10,
    }),
  );
  eventServiceMock.registerForEvent.mockRejectedValueOnce({
    response: { data: { detail: 'registration failed' } },
  });
  renderEventDetail('/events/1');
  await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

  fireEvent.click(screen.getByRole('button', { name: /Back/i }));
  expect(navigateSpy).toHaveBeenCalledWith(-1);

  const coverImage = screen.getByRole('img', { name: /AI Summit/i });
  fireEvent.error(coverImage);
  expect(coverImage).toHaveAttribute(
    'src',
    expect.stringContaining('images.unsplash.com/photo-1540575467063-178a50c2df87'),
  );

  fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
  await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 20000);
