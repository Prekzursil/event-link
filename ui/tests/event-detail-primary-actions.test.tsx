import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  defineMutableValue,
  renderLanguageRoute,
  requireElement,
} from './page-test-helpers';
import { EventDetailPage, getEventDetailFixtures } from './event-detail-branches.shared';

const { authState, eventServiceMock, navigateSpy, toastSpy } = getEventDetailFixtures();

/**
 * Renders the event detail scaffolding for tests.
 */
function renderEventDetail(path = '/events/1') {
  return renderLanguageRoute(path, '/events/:id', <EventDetailPage />);
}

/**
 * Builds a event fixture.
 */
function makeEvent(overrides?: Partial<Record<string, unknown>>) {
  return {
    id: 1,
    title: 'AI Summit',
    description: 'Detailed event description',
    category: 'Technical',
    start_time: new Date(Date.now() + 3_600_000).toISOString(),
    end_time: new Date(Date.now() + 7_200_000).toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 50,
    seats_taken: 10,
    available_seats: 40,
    tags: [{ id: 5, name: 'Tech' }],
    owner_id: 9,
    owner_name: 'Organizer Name',
    recommendation_reason: 'Recommended for your profile',
    is_owner: false,
    is_registered: false,
    is_favorite: false,
    status: 'published',
    cover_url: '',
    ...overrides,
  };
}

describe('event detail primary actions', () => {
  it('covers load failure branch and redirects to home', async () => {
    eventServiceMock.getEvent.mockRejectedValueOnce(new Error('not-found'));
    renderEventDetail('/events/999');

    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/');
  });

  it('covers unauthenticated register and favorite redirect branch', async () => {
    authState.isAuthenticated = false;
    authState.user = null;
    renderEventDetail('/events/1');

    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(await screen.findByRole('button', { name: /Register for event/i }));
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith('/login', {
        state: { from: { pathname: '/events/1' } },
      }),
    );

    const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
    const actionButtons = within(
      requireElement(addToCalendarButton.parentElement, 'calendar action group'),
    ).getAllByRole('button');
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledTimes(2));
  });

  it('covers register, favorite, share, and export branches for an authenticated student', async () => {
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(await screen.findByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));

    const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
    const actionButtons = within(
      requireElement(addToCalendarButton.parentElement, 'calendar action group'),
    ).getAllByRole('button');

    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));

    eventServiceMock.removeFromFavorites.mockRejectedValueOnce(new Error('fav-remove-fail'));
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(actionButtons[1]);
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());

    defineMutableValue(navigator, 'share', vi.fn().mockResolvedValue());
    fireEvent.click(actionButtons[1]);
    await waitFor(() => expect(navigator.share).toHaveBeenCalled());

    fireEvent.click(addToCalendarButton);
    expect(globalThis.open).toHaveBeenCalled();
  }, 20000);

  it('covers registered attendee resend and unregister success and fallback branches', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(makeEvent({ is_registered: true }));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(eventServiceMock.resendRegistrationEmail).toHaveBeenCalledWith(1));

    eventServiceMock.resendRegistrationEmail.mockRejectedValueOnce(new Error('resend-fail'));
    fireEvent.click(await screen.findByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.unregisterFromEvent.mockRejectedValueOnce(new Error('unregister-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Unregister/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);
});
