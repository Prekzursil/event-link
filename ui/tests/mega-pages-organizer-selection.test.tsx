import { cleanup, fireEvent, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  AdminDashboardPage,
  OrganizerDashboardPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import { renderLanguageRoute } from './page-test-helpers';

const { adminServiceMock, eventServiceMock } = getMegaPageFixtures();

it('covers the users previous-page handler and organizer deselection branch', async () => {
  adminServiceMock.getUsers.mockResolvedValue({
    items: [
      {
        id: 1,
        email: 'student@test.local',
        full_name: 'Student Name',
        role: 'student',
        is_active: true,
        created_at: new Date().toISOString(),
        last_seen_at: new Date().toISOString(),
        registrations_count: 2,
        attended_count: 1,
        events_created_count: 0,
      },
    ],
    total: 40,
    page: 2,
    page_size: 20,
  });

  renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
  const usersTab = await screen.findByRole('tab', { name: /Users/i });
  fireEvent.mouseDown(usersTab);
  fireEvent.click(usersTab);
  await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());
  await waitForElementToBeRemoved(() => screen.queryByText(/Loading users/i));

  const usersPrevButtons = await screen.findAllByRole('button', {
    name: /Back|Prev|Previous|Înapoi|Anterior/i,
  });
  usersPrevButtons.forEach((button) => {
    if (!button.hasAttribute('disabled')) {
      fireEvent.click(button);
    }
  });
  await waitFor(() =>
    expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })),
  );

  cleanup();
  renderLanguageRoute('/organizer', '/organizer', <OrganizerDashboardPage />);
  await waitFor(() => expect(eventServiceMock.getOrganizerEvents).toHaveBeenCalled());

  const organizerCheckboxes = screen.getAllByRole('checkbox');
  const rowCheckbox = organizerCheckboxes[organizerCheckboxes.length - 1];
  fireEvent.click(rowCheckbox);
  await waitFor(() => expect(screen.getByRole('button', { name: /Publish|Public/i })).toBeInTheDocument());
  fireEvent.click(rowCheckbox);
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: /Publish|Public/i })).not.toBeInTheDocument(),
  );
}, 20000);
