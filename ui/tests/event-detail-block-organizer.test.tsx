import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { getEventDetailFixtures } from './event-detail-branches.shared';
import {
  makeEvent,
  renderEventDetail,
} from './event-detail-owner-preferences.shared';

const { eventServiceMock, toastSpy } = getEventDetailFixtures();

it('covers block-organizer success and error branches', async () => {
  eventServiceMock.getEvent.mockResolvedValueOnce(
    makeEvent({ is_favorite: true, recommendation_reason: '', tags: [{ id: 7, name: 'AI' }] }),
  );
  renderEventDetail('/events/1');
  await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

  const blockButton = screen.getByRole('button', {
    name: /Block organizer|Blochează organizator/i,
  });
  fireEvent.click(blockButton);
  await waitFor(() => expect(eventServiceMock.blockOrganizer).toHaveBeenCalledWith(9));

  eventServiceMock.blockOrganizer.mockRejectedValueOnce({
    response: { data: { detail: 'block-failed' } },
  });
  fireEvent.click(blockButton);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 20000);
