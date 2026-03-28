import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  ParticipantsPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import { renderLanguageRoute } from './page-test-helpers';
import {
  makeParticipant,
  makeParticipantsPage,
} from './page-test-data';

const { eventServiceMock, toastSpy } = getMegaPageFixtures();

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
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'registration_time', 'asc'),
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
