import { cleanup, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventFormPage,
  OrganizerDashboardPage,
  OrganizerProfilePage,
  ParticipantsPage,
  getMegaPagesSmokeFixtures,
} from './mega-pages-smoke.shared';

const { eventServiceMock, toastSpy } = getMegaPagesSmokeFixtures();

describe('mega pages organizer smoke', () => {
  it('covers organizer page success flows', async () => {
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());
    expect(await screen.findByText(/Event 3/i)).toBeInTheDocument();

    cleanup();
    renderLanguageRoute('/organizer/events/3/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(3));

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

    cleanup();
    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/Organizer Team/i)).toBeInTheDocument();
  });

  it('covers organizer page error branches', async () => {
    eventServiceMock.getOrganizerEvents.mockRejectedValueOnce(new Error('org-events-fail'));
    renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    cleanup();
    eventServiceMock.getOrganizerProfile.mockRejectedValueOnce(new Error('org-profile-fail'));
    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(screen.getByText(/Organizer not found/i)).toBeInTheDocument());
  });
});
