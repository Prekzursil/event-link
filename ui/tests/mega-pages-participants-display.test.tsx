import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  ParticipantsPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import { renderLanguageRoute } from './page-test-helpers';
import {
  makeParticipant,
} from './page-test-data';

const { eventServiceMock } = getMegaPageFixtures();

it('covers participants route guards and populated display branches', async () => {
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
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'),
  );
  expect(screen.getByText('-')).toBeInTheDocument();

  const pendingAttendance = new Promise<void>(() => {
    /* never resolves — exercises pending-request branch */
  });
  eventServiceMock.updateParticipantAttendance.mockReturnValueOnce(pendingAttendance);
  const participantCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
  fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
  expect(eventServiceMock.updateParticipantAttendance).toHaveBeenCalledTimes(1);
}, 20000);

it('covers participants export, sorting, and empty-state branches', async () => {
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
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'),
  );
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
