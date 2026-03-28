import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { getEventDetailFixtures } from './event-detail-branches.shared';
import {
  makeEvent,
  renderEventDetail,
} from './event-detail-owner-preferences.shared';
import { requireElement } from './page-test-helpers';

const { eventServiceMock, recordInteractionsSpy, toastSpy } =
  getEventDetailFixtures();

it('covers favorite removal and hide-tag success and error branches', async () => {
  eventServiceMock.getEvent.mockResolvedValueOnce(
    makeEvent({ is_favorite: true, recommendation_reason: '', tags: [{ id: 7, name: 'AI' }] }),
  );
  renderEventDetail('/events/1');
  await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

  const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
  const actionButtons = within(
    requireElement(addToCalendarButton.parentElement, 'calendar action group'),
  ).getAllByRole('button');
  fireEvent.click(actionButtons[0]);
  await waitFor(() => expect(eventServiceMock.removeFromFavorites).toHaveBeenCalledWith(1));
  await waitFor(() => {
    const payloads = recordInteractionsSpy.mock.calls.flatMap(([payload]) => payload);
    expect(payloads).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          interaction_type: 'favorite',
          meta: expect.objectContaining({ action: 'remove' }),
        }),
      ]),
    );
  });

  const hideButton = screen.getByRole('button', { name: /Hide|Ascunde/i });
  fireEvent.click(hideButton);
  expect(eventServiceMock.hideTag).not.toHaveBeenCalled();

  const tagSelect = screen.getByRole('combobox');
  fireEvent.click(tagSelect);
  fireEvent.click(await screen.findByRole('option', { name: /AI/i }));
  fireEvent.click(hideButton);
  await waitFor(() => expect(eventServiceMock.hideTag).toHaveBeenCalledWith(7));

  fireEvent.click(tagSelect);
  fireEvent.click(await screen.findByRole('option', { name: /AI/i }));
  eventServiceMock.hideTag.mockRejectedValueOnce({
    response: { data: { detail: 'hide-tag-failed' } },
  });
  fireEvent.click(hideButton);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 20000);

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
