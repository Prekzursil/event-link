import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  AdminDashboardPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import { renderLanguageRoute } from './page-test-helpers';

const { adminServiceMock, eventServiceMock } = getMegaPageFixtures();

it('covers admin dashboard queue, user, and event action branches', async () => {
  renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
  await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());

  fireEvent.click(await screen.findByRole('button', { name: /Retrain/i }));
  await waitFor(() => expect(adminServiceMock.enqueueRecommendationsRetrain).toHaveBeenCalled());
  fireEvent.click(await screen.findByRole('button', { name: /Digest/i }));
  await waitFor(() => expect(adminServiceMock.enqueueWeeklyDigest).toHaveBeenCalled());
  fireEvent.click(await screen.findByRole('button', { name: /Filling-fast/i }));
  await waitFor(() => expect(adminServiceMock.enqueueFillingFast).toHaveBeenCalled());

  const usersTab = screen.getByRole('tab', { name: /Users/i });
  fireEvent.mouseDown(usersTab);
  fireEvent.click(usersTab);
  await waitFor(() => expect(usersTab).toHaveAttribute('data-state', 'active'));
  await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
  await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalledTimes(2));

  const checkboxes = screen.getAllByRole('checkbox');
  fireEvent.click(checkboxes[checkboxes.length - 1]);
  await waitFor(() => expect(adminServiceMock.updateUser).toHaveBeenCalled());

  const eventsTab = screen.getByRole('tab', { name: /Events/i });
  fireEvent.mouseDown(eventsTab);
  fireEvent.click(eventsTab);
  await waitFor(() => expect(eventsTab).toHaveAttribute('data-state', 'active'));
  await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
  await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalledTimes(2));

  fireEvent.click(screen.getByRole('button', { name: /Mark reviewed/i }));
  await waitFor(() => expect(adminServiceMock.reviewEventModeration).toHaveBeenCalledWith(21));
  fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
  await waitFor(() => expect(eventServiceMock.deleteEvent).toHaveBeenCalledWith(21));
  fireEvent.click(screen.getByRole('button', { name: /Restore/i }));
  await waitFor(() => expect(eventServiceMock.restoreEvent).toHaveBeenCalledWith(22));
}, 30000);
