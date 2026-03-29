import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  OrganizerDashboardPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import { renderLanguageRoute } from './page-test-helpers';
import { makeOrganizerEvent } from './page-test-data';

const { eventServiceMock } = getMegaPageFixtures();

it('covers organizer dashboard display, bulk tags, and status actions', async () => {
  eventServiceMock.getOrganizerEvents.mockResolvedValueOnce([
    makeOrganizerEvent(3),
    makeOrganizerEvent(4, {
      start_time: new Date(Date.now() - 3_600_000).toISOString(),
    }),
  ]);

  renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
  await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());
  expect(screen.getByText(/Ended/i)).toBeInTheDocument();

  const organizerCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);
  expect(screen.getAllByRole('checkbox')[0]).toHaveAttribute('data-state', 'indeterminate');

  const draftButton = screen.getByRole('button', { name: /Unpublish|Set as draft|Draft/i });
  const initialStatusCallCount = eventServiceMock.bulkUpdateEventStatus.mock.calls.length;
  fireEvent.click(draftButton);
  expect(eventServiceMock.bulkUpdateEventStatus.mock.calls).toHaveLength(initialStatusCallCount);
  fireEvent.click(draftButton);
  await waitFor(() =>
    expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenLastCalledWith(
      expect.any(Array),
      'draft',
    ),
  );

  const organizerCheckboxesAfterDraft = screen.getAllByRole('checkbox');
  fireEvent.click(organizerCheckboxesAfterDraft[organizerCheckboxesAfterDraft.length - 1]);
  fireEvent.click(screen.getByRole('button', { name: /Set tags/i }));
  const bulkTagsDialog = await screen.findByRole('dialog');
  fireEvent.click(within(bulkTagsDialog).getByRole('button', { name: /Add/i }));
  expect(screen.queryByText('bulk-tag')).not.toBeInTheDocument();

  const bulkTagInput = screen.getByPlaceholderText(/Add a tag/i);
  fireEvent.change(bulkTagInput, { target: { value: 'bulk-tag' } });
  fireEvent.click(within(bulkTagsDialog).getByRole('button', { name: /Add/i }));
  expect(await screen.findByText('bulk-tag')).toBeInTheDocument();
  fireEvent.change(bulkTagInput, { target: { value: 'bulk-tag' } });
  fireEvent.click(within(bulkTagsDialog).getByRole('button', { name: /Add/i }));
  expect(screen.getAllByText('bulk-tag')).toHaveLength(1);
  fireEvent.click(within(bulkTagsDialog).getByRole('button', { name: /Cancel/i }));

  fireEvent.click(screen.getByRole('button', { name: /Publish|Public/i }));
  await waitFor(() =>
    expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([4], 'published'),
  );
}, 20000);
