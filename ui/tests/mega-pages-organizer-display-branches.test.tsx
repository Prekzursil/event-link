import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  OrganizerDashboardPage,
  ParticipantsPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import {
  makeOrganizerEvent,
  makeParticipant,
  makeParticipantsPage,
} from './page-test-data';

const { eventServiceMock, toastSpy } = getMegaPageFixtures();

it('covers organizer dashboard and participants display edge branches', async () => {
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

  vi.mocked(globalThis.confirm).mockReturnValueOnce(false);
  fireEvent.click(screen.getByRole('button', { name: /Unpublish|Set as draft|Draft/i }));
  expect(eventServiceMock.bulkUpdateEventStatus).not.toHaveBeenCalledWith([3], 'draft');

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

  cleanup();
  renderLanguageRoute(
    '/organizer/events/participants',
    '/organizer/events/participants',
    <ParticipantsPage />,
  );
  expect(eventServiceMock.getEventParticipants).not.toHaveBeenCalled();

  cleanup();
  eventServiceMock.getEventParticipants.mockResolvedValueOnce({
    event_id: 3,
    title: 'Organizer event',
    seats_taken: 1,
    max_seats: 30,
    participants: [makeParticipant(10, { attended: true, full_name: '' })],
    total: 1,
    page: 1,
    page_size: 20,
  });

  renderLanguageRoute(
    '/organizer/events/3/participants',
    '/organizer/events/:id/participants',
    <ParticipantsPage />,
  );
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
      3,
      1,
      20,
      'registration_time',
      'asc',
    ),
  );
  expect(screen.getByText('-')).toBeInTheDocument();

  const pendingAttendance = new Promise<void>(() => {});
  eventServiceMock.updateParticipantAttendance.mockReturnValueOnce(pendingAttendance);
  const participantCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
  expect(eventServiceMock.updateParticipantAttendance).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));
  expect(URL.createObjectURL).toHaveBeenCalled();

  const participantsTable = screen.getByRole('table');
  const emailSortButton = within(participantsTable).getByRole('button', { name: /Email/i });
  fireEvent.click(emailSortButton);
  fireEvent.click(emailSortButton);
  fireEvent.click(emailSortButton);

  cleanup();
  eventServiceMock.getEventParticipants.mockResolvedValueOnce({
    event_id: 3,
    title: 'Organizer event',
    seats_taken: 0,
    max_seats: 30,
    participants: [],
    total: 0,
    page: 1,
    page_size: 20,
  });
  renderLanguageRoute(
    '/organizer/events/3/participants',
    '/organizer/events/:id/participants',
    <ParticipantsPage />,
  );
  await waitFor(() => expect(screen.getByText(/No participants/i)).toBeInTheDocument());
}, 20000);

it('covers participants attendance clearing and mixed CSV export branches', async () => {
  eventServiceMock.getEventParticipants.mockResolvedValueOnce(
    makeParticipantsPage(3, {
      participants: [
        makeParticipant(10, {
          attended: true,
          email: 'first@test.local',
          full_name: 'First Participant',
        }),
        makeParticipant(11, {
          attended: false,
          email: 'second@test.local',
          full_name: '',
        }),
      ],
      total: 2,
      page: 1,
      page_size: 20,
    }),
  );

  renderLanguageRoute(
    '/organizer/events/3/participants',
    '/organizer/events/:id/participants',
    <ParticipantsPage />,
  );
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
      3,
      1,
      20,
      'registration_time',
      'asc',
    ),
  );

  fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));
  expect(URL.createObjectURL).toHaveBeenCalled();

  const participantCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 2]);
  await waitFor(() =>
    expect(eventServiceMock.updateParticipantAttendance).toHaveBeenCalledWith(3, 10, false),
  );

  eventServiceMock.updateParticipantAttendance.mockRejectedValueOnce(
    new Error('attendance-fail'),
  );
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 20000);
