import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  OrganizerDashboardPage,
  ParticipantsPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';

const { eventServiceMock, navigateSpy, toastSpy } = getMegaPageFixtures();

/** Exercise organizer dashboard and participants callbacks that only occur on edge branches. */
async function coverOrganizerAndParticipantsCallbackEdgeBranches() {
  renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
  await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());
  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(0));

  const organizerCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);
  fireEvent.click(screen.getByRole('button', { name: /Publish|Public/i }));
  await waitFor(() =>
    expect(eventServiceMock.bulkUpdateEventStatus).toHaveBeenCalledWith([3], 'published'),
  );

  fireEvent.click(organizerCheckboxes[0]);
  fireEvent.click(organizerCheckboxes[0]);
  fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);

  eventServiceMock.bulkUpdateEventStatus.mockRejectedValueOnce(new Error('bulk-status-fail'));
  fireEvent.click(screen.getByRole('button', { name: /Publish/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.click(screen.getByRole('button', { name: /Clear selection/i }));

  fireEvent.click(organizerCheckboxes[organizerCheckboxes.length - 1]);
  fireEvent.click(screen.getByRole('button', { name: /Set tags/i }));
  fireEvent.change(screen.getByPlaceholderText(/Add a tag/i), { target: { value: 'bulk-tag' } });
  fireEvent.click(screen.getByRole('button', { name: /^Add$/i }));
  eventServiceMock.bulkUpdateEventTags.mockRejectedValueOnce(new Error('bulk-tags-fail'));
  fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));

  vi.mocked(globalThis.confirm).mockReturnValueOnce(true);
  eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
  fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  vi.mocked(globalThis.confirm).mockReturnValueOnce(false);
  fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
  expect(eventServiceMock.deleteEvent).toHaveBeenCalledTimes(1);

  vi.mocked(globalThis.confirm).mockReturnValueOnce(true);
  eventServiceMock.deleteEvent.mockResolvedValueOnce();
  fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
  await waitFor(() => expect(eventServiceMock.deleteEvent).toHaveBeenCalledWith(3));

  cleanup();
  eventServiceMock.getEventParticipants.mockRejectedValueOnce(
    new Error('participants-load-fail'),
  );
  renderLanguageRoute(
    '/organizer/events/3/participants',
    '/organizer/events/:id/participants',
    <ParticipantsPage />,
  );
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  cleanup();
  eventServiceMock.getEventParticipants.mockResolvedValue({
    event_id: 3,
    title: 'Organizer event',
    seats_taken: 3,
    max_seats: 30,
    participants: [
      {
        id: 10,
        email: 'participant@test.local',
        full_name: 'Participant',
        registration_time: new Date().toISOString(),
        attended: false,
      },
    ],
    total: 40,
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

  fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
  const emailOpenDialog = await screen.findByRole('dialog');
  fireEvent.click(within(emailOpenDialog).getByRole('button', { name: /Cancel/i }));
  const participantsTable = screen.getByRole('table');
  const participantsSortButtons = within(participantsTable).getAllByRole('button');
  fireEvent.click(participantsSortButtons[0]);
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(3, 1, 20, 'email', 'asc'),
  );

  fireEvent.click(participantsSortButtons[1]);
  fireEvent.click(participantsSortButtons[2]);
  await waitFor(() => expect(eventServiceMock.getEventParticipants).toHaveBeenCalled());
  const participantsPageText =
    screen.getAllByText(/Page/i).find((node) => /of/i.test(node.textContent || '')) ?? null;
  expect(participantsPageText).not.toBeNull();
  const participantsPageContainer = participantsPageText?.closest('div')?.parentElement;
  const participantsPagerButtons = within(
    requireElement(participantsPageContainer, 'participants page container'),
  ).getAllByRole('button');
  fireEvent.click(participantsPagerButtons[participantsPagerButtons.length - 1]);
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
      3,
      2,
      20,
      'registration_time',
      'asc',
    ),
  );
  fireEvent.click(participantsPagerButtons[participantsPagerButtons.length - 2]);
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
      3,
      1,
      20,
      'registration_time',
      'asc',
    ),
  );

  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBeGreaterThan(0));

  const participantsCheckboxes = screen.getAllByRole('checkbox');
  fireEvent.click(participantsCheckboxes[participantsCheckboxes.length - 1]);
  await waitFor(() =>
    expect(eventServiceMock.updateParticipantAttendance).toHaveBeenCalledWith(3, 10, true),
  );

  fireEvent.click(screen.getByRole('button', { name: /Email participants/i }));
  const dialog = await screen.findByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.change(screen.getByLabelText(/Subject/i), { target: { value: 'Subject' } });
  fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.change(screen.getByLabelText(/Message/i), { target: { value: 'Body' } });
  eventServiceMock.emailEventParticipants.mockRejectedValueOnce(new Error('email-fail'));
  fireEvent.click(within(dialog).getByRole('button', { name: /^Send$/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.click(within(dialog).getByRole('button', { name: /Cancel/i }));

  fireEvent.click(screen.getByRole('button', { name: /^50$/i }));
  await waitFor(() =>
    expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
      3,
      1,
      50,
      'registration_time',
      'asc',
    ),
  );

  const paginationText = screen.queryByText(/Page/i);
  if (paginationText) {
    const paginationContainer = paginationText.closest('div');
    if (paginationContainer) {
      const paginationButtons = within(paginationContainer).getAllByRole('button');
      fireEvent.click(paginationButtons[paginationButtons.length - 1]);
      await waitFor(() =>
        expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
          3,
          2,
          50,
          'registration_time',
          'asc',
        ),
      );
      fireEvent.click(paginationButtons[0]);
      await waitFor(() =>
        expect(eventServiceMock.getEventParticipants).toHaveBeenCalledWith(
          3,
          1,
          50,
          'registration_time',
          'asc',
        ),
      );
    }
  }

  fireEvent.click(screen.getByRole('button', { name: /Back to dashboard/i }));
  expect(navigateSpy).toHaveBeenCalledWith('/organizer');
}

describe('mega pages organizer edge branches', () => {
  it('covers organizer and participants callback edge branches', async () => {
    await coverOrganizerAndParticipantsCallbackEdgeBranches();
  }, 25000);
});
