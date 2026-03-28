import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  OrganizerDashboardPage,
  ParticipantsPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';

const { eventServiceMock, toastSpy } = getMegaPageFixtures();

describe('mega pages organizer actions', () => {
  it('covers organizer bulk actions and participant email, CSV, and sort flows', async () => {
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

    const organizerCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(organizerCheckboxes[0]);
    fireEvent.click(screen.getByRole('button', { name: /Publish/i }));
    await waitFor(() =>
      expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'),
    );

    cleanup();
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

    fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Subject/i), {
      target: { value: 'Hello participants' },
    });
    fireEvent.change(screen.getByLabelText(/Message/i), {
      target: { value: 'Thanks for joining.' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /Send/i }));
    await waitFor(() =>
      expect(eventServiceMock.emailEventParticipants).toHaveBeenCalledWith(
        3,
        'Hello participants',
        'Thanks for joining.',
      ),
    );

    fireEvent.click(screen.getByRole('button', { name: /Export CSV/i }));
    expect(URL.createObjectURL).toHaveBeenCalled();

    eventServiceMock.updateParticipantAttendance.mockRejectedValueOnce(
      new Error('attendance-fail'),
    );
    const participantCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(participantCheckboxes[participantCheckboxes.length - 1]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Registration date/i }));
    await waitFor(() =>
      expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
        3,
        1,
        20,
        'registration_time',
        'desc',
      ),
    );
  });
});
