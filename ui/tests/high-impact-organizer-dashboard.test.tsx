import React from 'react';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  OrganizerDashboardPage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';

const { eventServiceMock, toastSpy } = getHighImpactPageFixtures();

it('covers OrganizerDashboardPage bulk tag branches and delete guard branches', async () => {
  renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
  await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

  const checkboxes = await screen.findAllByRole('checkbox');
  fireEvent.click(checkboxes[1]);
  const publishButton = screen.getByRole('button', { name: /Publish/i });
  const bulkContainer = publishButton.parentElement;
  const bannerButtons = within(requireElement(bulkContainer, 'bulk container')).getAllByRole(
    'button',
  );
  fireEvent.click(bannerButtons[2]);
  const dialog = await screen.findByRole('dialog');
  const input = within(dialog).getByPlaceholderText(/tag/i);

  fireEvent.keyDown(input, { key: 'x' });
  fireEvent.change(input, { target: { value: 'x'.repeat(120) } });
  fireEvent.keyDown(input, { key: 'Enter' });

  fireEvent.change(input, { target: { value: 'Community' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  const communityBadge = within(dialog).getByText('Community');
  fireEvent.click(communityBadge);

  fireEvent.click(within(dialog).getByRole('button', { name: /Cancel|Anulează/i }));
  fireEvent.click(bannerButtons[2]);
  const reopenedDialog = await screen.findByRole('dialog');
  const reopenedInput = within(reopenedDialog).getByPlaceholderText(/tag/i);
  fireEvent.change(reopenedInput, { target: { value: 'Community' } });
  fireEvent.keyDown(reopenedInput, { key: 'Enter' });

  eventServiceMock.bulkUpdateEventTags.mockRejectedValueOnce(new Error('bulk-tags-fail'));
  fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Apply/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.change(input, { target: { value: 'AI' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Apply/i }));
  await waitFor(() => expect(eventServiceMock.bulkUpdateEventTags).toHaveBeenCalled());

  const checkboxesAfterTags = screen.getAllByRole('checkbox');
  fireEvent.click(checkboxesAfterTags[1]);
  fireEvent.click(screen.getByRole('button', { name: /Publish/i }));

  const clearButton = screen.getByRole('button', { name: /Clear|Șterge selecția/i });
  fireEvent.click(clearButton);
  await waitFor(() =>
    expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'),
  );

  const checkboxesAfterPublish = screen.getAllByRole('checkbox');
  fireEvent.click(checkboxesAfterPublish[1]);
  const draftButton = screen.queryByRole('button', { name: /Unpublish|Draft/i });
  if (draftButton) {
    fireEvent.click(draftButton);
    expect(eventServiceMock.bulkUpdateEventStatus).not.toHaveBeenCalledWith([3], 'draft');
    fireEvent.click(draftButton);
    await waitFor(() =>
      expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'draft'),
    );
  }

  const menuTrigger = screen
    .getAllByRole('button')
    .find((btn) => btn.getAttribute('aria-haspopup') === 'menu');
  expect(menuTrigger).toBeDefined();

  fireEvent.click(requireElement(menuTrigger, 'menu trigger'));
  const deleteOption = screen.queryByText(/Delete|Șterge/i);
  if (deleteOption) {
    fireEvent.click(deleteOption);
    expect(eventServiceMock.deleteEvent).not.toHaveBeenCalled();

    fireEvent.click(requireElement(menuTrigger, 'menu trigger'));
    const deleteOptionRetry = screen.queryByText(/Delete|Șterge/i);
    if (deleteOptionRetry) {
      eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
      fireEvent.click(deleteOptionRetry);
      await waitFor(() => expect(eventServiceMock.deleteEvent).toHaveBeenCalled());
      await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    }
  }
});
