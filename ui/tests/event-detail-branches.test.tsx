import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { defineMutableValue, renderLanguageRoute, requireElement, setEnglishPreference } from './page-test-helpers';

const { eventServiceMock, recordInteractionsSpy, authState, toastSpy, navigateSpy } = vi.hoisted(() => ({
  eventServiceMock: {
    getEvent: vi.fn(),
    registerForEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    cloneEvent: vi.fn(),
    hideTag: vi.fn(),
    blockOrganizer: vi.fn(),
  },
  recordInteractionsSpy: vi.fn(),
  authState: {
    isAuthenticated: true,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
}));

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/analytics.service', () => ({ recordInteractions: recordInteractionsSpy }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { EventDetailPage } from '@/pages/events/EventDetailPage';

function renderEventDetail(path = '/events/1') {
  return renderLanguageRoute(path, '/events/:id', <EventDetailPage />);
}

function makeEvent(overrides?: Partial<Record<string, unknown>>) {
  return {
    id: 1,
    title: 'AI Summit',
    description: 'Detailed event description',
    category: 'Technical',
    start_time: new Date(Date.now() + 3600000).toISOString(),
    end_time: new Date(Date.now() + 7200000).toISOString(),
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

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();

  defineMutableValue(globalThis, 'open', vi.fn());
  defineMutableValue(navigator, 'clipboard', {
    writeText: vi.fn().mockResolvedValue(undefined),
  });
  defineMutableValue(navigator, 'share', undefined);
  defineMutableValue(HTMLElement.prototype, 'scrollIntoView', vi.fn());

  authState.isAuthenticated = true;
  authState.user = { id: 1, role: 'student', email: 'student@test.local' };

  eventServiceMock.getEvent.mockResolvedValue(makeEvent());
  eventServiceMock.registerForEvent.mockResolvedValue(undefined);
  eventServiceMock.unregisterFromEvent.mockResolvedValue(undefined);
  eventServiceMock.resendRegistrationEmail.mockResolvedValue(undefined);
  eventServiceMock.addToFavorites.mockResolvedValue(undefined);
  eventServiceMock.removeFromFavorites.mockResolvedValue(undefined);
  eventServiceMock.cloneEvent.mockResolvedValue({ id: 77 });
  eventServiceMock.hideTag.mockResolvedValue(undefined);
  eventServiceMock.blockOrganizer.mockResolvedValue(undefined);
});

describe('event detail branch coverage', () => {
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

    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith('/login', { state: { from: { pathname: '/events/1' } } }),
    );

    const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
    const actionButtons = within(requireElement(addToCalendarButton.parentElement, 'calendar action group')).getAllByRole('button');
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledTimes(2));
  });

  it('covers register/favorite/share/export branches for authenticated student', async () => {
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));

    const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
    const actionButtons = within(requireElement(addToCalendarButton.parentElement, 'calendar action group')).getAllByRole('button');

    // Favorite add success then remove error.
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(eventServiceMock.addToFavorites).toHaveBeenCalledWith(1));

    eventServiceMock.removeFromFavorites.mockRejectedValueOnce(new Error('fav-remove-fail'));
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    // Share fallback path (clipboard).
    fireEvent.click(actionButtons[1]);
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());

    // Share native path.
    defineMutableValue(navigator, 'share', vi.fn().mockResolvedValue(undefined));
    fireEvent.click(actionButtons[1]);
    await waitFor(() => expect(navigator.share).toHaveBeenCalled());

    // Export calendar path.
    fireEvent.click(addToCalendarButton);
    expect(globalThis.open).toHaveBeenCalled();
  }, 20000);

  it('covers registered attendee resend/unregister success and fallback branches', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(makeEvent({ is_registered: true }));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(eventServiceMock.resendRegistrationEmail).toHaveBeenCalledWith(1));

    eventServiceMock.resendRegistrationEmail.mockRejectedValueOnce(new Error('resend-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.unregisterFromEvent.mockRejectedValueOnce(new Error('unregister-fail'));
    fireEvent.click(screen.getByRole('button', { name: /Unregister/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers owner clone success and error branches', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(makeEvent({ is_owner: true, is_registered: false }));
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
    await waitFor(() => expect(eventServiceMock.cloneEvent).toHaveBeenCalledWith(1));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer/events/77/edit');

    eventServiceMock.cloneEvent.mockRejectedValueOnce(new Error('clone-failed'));
    fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);
  it('covers register error rollback, back navigation and cover fallback image', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        cover_url: 'https://example.com/broken.jpg',
        description: '',
        status: 'draft',
        max_seats: 10,
        available_seats: 10,
      }),
    );
    eventServiceMock.registerForEvent.mockRejectedValueOnce({
      response: { data: { detail: 'registration failed' } },
    });

    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    expect(navigateSpy).toHaveBeenCalledWith(-1);

    const coverImage = screen.getByRole('img', { name: /AI Summit/i });
    fireEvent.error(coverImage);
    expect(coverImage).toHaveAttribute('src', expect.stringContaining('images.unsplash.com/photo-1540575467063-178a50c2df87'));

    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers favorite remove success, hide-tag success/error and block-organizer success/error', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({
        is_favorite: true,
        recommendation_reason: '',
        tags: [{ id: 7, name: 'AI' }],
      }),
    );

    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    const addToCalendarButton = screen.getByRole('button', { name: /Add to calendar/i });
    const actionButtons = within(requireElement(addToCalendarButton.parentElement, 'calendar action group')).getAllByRole('button');
    fireEvent.click(actionButtons[0]);
    await waitFor(() => expect(eventServiceMock.removeFromFavorites).toHaveBeenCalledWith(1));
    await waitFor(
      () => {
        const payloads = recordInteractionsSpy.mock.calls.flatMap(([payload]) => payload);
        expect(payloads).toEqual(
          expect.arrayContaining([
            expect.objectContaining({
              interaction_type: 'favorite',
              meta: expect.objectContaining({ action: 'remove' }),
            }),
          ]),
        );
      },
      { timeout: 5000 },
    );

    const hideButton = screen.getByRole('button', { name: /Hide|Ascunde/i });
    fireEvent.click(hideButton);
    expect(eventServiceMock.hideTag).not.toHaveBeenCalled();

    const tagSelect = screen.getByRole('combobox');
    fireEvent.click(tagSelect);
    fireEvent.click(await screen.findByRole('option', { name: /AI/i }));

    fireEvent.click(hideButton);
    await waitFor(() => expect(eventServiceMock.hideTag).toHaveBeenCalledWith(7));

    fireEvent.click(tagSelect);
    fireEvent.click(await screen.findByRole('option', { name: /AI/i }));
    eventServiceMock.hideTag.mockRejectedValueOnce({
      response: { data: { detail: 'hide-tag-failed' } },
    });
    fireEvent.click(hideButton);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    const blockButton = screen.getByRole('button', { name: /Block organizer|Blochează organizator/i });
    fireEvent.click(blockButton);
    await waitFor(() => expect(eventServiceMock.blockOrganizer).toHaveBeenCalledWith(9));

    eventServiceMock.blockOrganizer.mockRejectedValueOnce({
      response: { data: { detail: 'block-failed' } },
    });
    fireEvent.click(blockButton);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);
});


