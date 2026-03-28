import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  AdminDashboardPage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';
import {
  makeAdminEvent,
  makeAdminUser,
  makePersonalizationMetrics,
} from './page-test-data';

const { adminServiceMock, eventServiceMock, toastSpy } = getMegaPageFixtures();

describe('mega pages admin fallbacks', () => {
  it('covers admin dashboard error branches, callbacks, and pagination controls', async () => {
    adminServiceMock.getStats.mockRejectedValueOnce(new Error('stats-fail'));
    adminServiceMock.getPersonalizationMetrics.mockRejectedValueOnce(new Error('metrics-fail'));
    adminServiceMock.getUsers.mockRejectedValueOnce(new Error('users-fail'));
    adminServiceMock.getEvents.mockRejectedValueOnce(new Error('events-fail'));
    adminServiceMock.enqueueRecommendationsRetrain.mockRejectedValueOnce(
      new Error('retrain-fail'),
    );
    adminServiceMock.enqueueWeeklyDigest.mockRejectedValueOnce(new Error('digest-fail'));
    adminServiceMock.enqueueFillingFast.mockRejectedValueOnce(new Error('filling-fail'));

    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Reload/i }));
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole('button', { name: /Retrain/i }));
    fireEvent.click(screen.getByRole('button', { name: /Digest/i }));
    fireEvent.click(screen.getByRole('button', { name: /Filling-fast/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    const usersTab = screen.getByRole('tab', { name: /Users/i });
    fireEvent.mouseDown(usersTab);
    fireEvent.click(usersTab);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/email \/ name|email \/ nume/i), {
      target: { value: 'student' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Admin$/i }));
    fireEvent.click(screen.getByRole('button', { name: /Inactive/i }));
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());

    adminServiceMock.updateUser.mockRejectedValueOnce(new Error('update-user-fail'));
    const usersRow = screen.getByText('student@test.local').closest('tr');
    fireEvent.click(
      within(requireElement(usersRow, 'users row')).getByRole('button', { name: /Admin/i }),
    );
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    adminServiceMock.getUsers.mockResolvedValueOnce({
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

    const usersNextButton = screen.getByRole('button', { name: /Next|Urm|Înainte/i });
    fireEvent.click(usersNextButton);
    await waitFor(() =>
      expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })),
    );

    await waitFor(() =>
      expect(screen.queryByText(/Loading users|Se încarcă utilizatorii/i)).not.toBeInTheDocument(),
    );
    const usersPrevButton = screen.getByRole('button', {
      name: /Back|Prev|Previous|Înapoi|Anterior/i,
    });
    fireEvent.click(usersPrevButton);
    await waitFor(() =>
      expect(adminServiceMock.getUsers).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })),
    );

    const eventsTab = screen.getByRole('tab', { name: /Events/i });
    fireEvent.mouseDown(eventsTab);
    fireEvent.click(eventsTab);
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/title \/ owner|titlu \/ owner/i), {
      target: { value: 'flagged' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Draft/i }));
    const eventsCheckboxes = screen.getAllByRole('checkbox');
    fireEvent.click(eventsCheckboxes[eventsCheckboxes.length - 2]);
    fireEvent.click(eventsCheckboxes[eventsCheckboxes.length - 1]);
    fireEvent.click(screen.getByRole('button', { name: /Apply/i }));
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());

    adminServiceMock.getEvents.mockResolvedValueOnce({
      items: [
        {
          id: 21,
          title: 'Admin flagged',
          description: 'flagged',
          category: 'Technical',
          start_time: new Date().toISOString(),
          end_time: new Date(Date.now() + 3_600_000).toISOString(),
          status: 'published',
          owner_id: 7,
          owner_email: 'org@test.local',
          owner_name: 'Organizer',
          seats_taken: 1,
          max_seats: 50,
          city: 'Cluj',
          location: 'Hall',
          tags: [],
          moderation_status: 'flagged',
          moderation_score: 0.91,
          moderation_flags: ['spam'],
          deleted_at: null,
        },
      ],
      total: 40,
      page: 2,
      page_size: 20,
    });
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));
    await waitFor(() =>
      expect(adminServiceMock.getEvents).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })),
    );
    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    await waitFor(() =>
      expect(adminServiceMock.getEvents).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })),
    );

    adminServiceMock.reviewEventModeration.mockRejectedValueOnce(new Error('review-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Mark reviewed/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.deleteEvent.mockRejectedValueOnce(new Error('delete-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.restoreEvent.mockRejectedValueOnce(new Error('restore-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Restore/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers admin dashboard loading and display fallback branches', async () => {
    let resolveMetrics: ((value: ReturnType<typeof makePersonalizationMetrics>) => void) | undefined;
    adminServiceMock.getPersonalizationMetrics.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveMetrics = resolve as (value: ReturnType<typeof makePersonalizationMetrics>) => void;
      }),
    );

    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());
    expect(screen.getByText(/Loading personalization metrics/i)).toBeInTheDocument();
    resolveMetrics?.(makePersonalizationMetrics());
    await waitFor(() =>
      expect(screen.queryByText(/Loading personalization metrics/i)).not.toBeInTheDocument(),
    );

    cleanup();
    adminServiceMock.getUsers.mockResolvedValueOnce({
      items: [
        makeAdminUser(1, { role: 'organizator', last_seen_at: null }),
        makeAdminUser(2, { email: 'second@test.local', role: 'student' }),
      ],
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
    const usersTab = await screen.findByRole('tab', { name: /Users/i });
    fireEvent.mouseDown(usersTab);
    fireEvent.click(usersTab);
    await waitFor(() => expect(adminServiceMock.getUsers).toHaveBeenCalled());
    expect(screen.getAllByText(/Organizer|Organizator/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);

    const organizerRow = screen.getByText(/student@test.local/i).closest('tr');
    fireEvent.click(
      within(requireElement(organizerRow, 'organizer user row')).getByRole('button', {
        name: /^Admin$/i,
      }),
    );
    await waitFor(() => expect(adminServiceMock.updateUser).toHaveBeenCalled());

    cleanup();
    adminServiceMock.getEvents.mockResolvedValueOnce({
      items: [
        makeAdminEvent(31, {
          moderation_status: undefined,
          city: '',
          moderation_flags: ['spam', 'fraud', 'scam', 'abuse'],
          max_seats: undefined,
          deleted_at: null,
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);
    const eventsTab = await screen.findByRole('tab', { name: /Events/i });
    fireEvent.mouseDown(eventsTab);
    fireEvent.click(eventsTab);
    await waitFor(() => expect(adminServiceMock.getEvents).toHaveBeenCalled());
    expect(document.body.textContent).toContain('spam, fraud, scam');
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);

    vi.mocked(globalThis.confirm).mockReturnValueOnce(false);
    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    expect(eventServiceMock.deleteEvent).not.toHaveBeenCalled();
  }, 20000);
});
