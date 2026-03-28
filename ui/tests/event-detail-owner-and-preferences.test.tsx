import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import { EventDetailPage, getEventDetailFixtures } from './event-detail-branches.shared';

const { eventServiceMock, navigateSpy, recordInteractionsSpy, toastSpy } =
  getEventDetailFixtures();

function renderEventDetail(path = '/events/1') {
  return renderLanguageRoute(path, '/events/:id', <EventDetailPage />);
}

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

describe('event detail owner and preference flows', () => {
  it('covers owner clone success and error branches', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce(
      makeEvent({ is_owner: true, is_registered: false }),
    );
    renderEventDetail('/events/1');
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));

    fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
    await waitFor(() => expect(eventServiceMock.cloneEvent).toHaveBeenCalledWith(1));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer/events/77/edit');

    eventServiceMock.cloneEvent.mockRejectedValueOnce(new Error('clone-failed'));
    fireEvent.click(await screen.findByRole('button', { name: /Duplicate event/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers register error rollback, back navigation, and the cover fallback image', async () => {
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
    expect(coverImage).toHaveAttribute(
      'src',
      expect.stringContaining('images.unsplash.com/photo-1540575467063-178a50c2df87'),
    );

    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() => expect(eventServiceMock.registerForEvent).toHaveBeenCalledWith(1));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);

  it('covers favorite removal, hide-tag, and block-organizer success and error branches', async () => {
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
    const actionButtons = within(
      requireElement(addToCalendarButton.parentElement, 'calendar action group'),
    ).getAllByRole('button');
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

    const blockButton = screen.getByRole('button', {
      name: /Block organizer|Blochează organizator/i,
    });
    fireEvent.click(blockButton);
    await waitFor(() => expect(eventServiceMock.blockOrganizer).toHaveBeenCalledWith(9));

    eventServiceMock.blockOrganizer.mockRejectedValueOnce({
      response: { data: { detail: 'block-failed' } },
    });
    fireEvent.click(blockButton);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 20000);
});
