import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { defineMutableValue, renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  EventsPage,
  getEventPagesFixtures,
  makeEvent,
} from './events-form-and-events-page.shared';

const { eventServiceMock, recordInteractionsSpy } = getEventPagesFixtures();

describe('events page filter branches', () => {
  it('covers media fallbacks, delayed cleanup, metadata fallbacks, and date filtering', async () => {
    defineMutableValue(globalThis, 'matchMedia');

    let rejectLateRequest: ((error: Error) => void) | undefined;
    eventServiceMock.getEvents.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectLateRequest = reject as (error: Error) => void;
      }),
    );
    const pendingRender = renderLanguageRoute('/events?search=late', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

    pendingRender.unmount();
    rejectLateRequest?.(new Error('late-fail'));
    await Promise.resolve();

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(30, 'Search only event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?search=solo&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(
      recordInteractionsSpy.mock.calls.some(([payload]) =>
        Array.isArray(payload) &&
        payload.some(
          (item: {
            interaction_type?: string;
            meta?: { category?: string; city?: string; location?: string };
          }) =>
            item?.interaction_type === 'search' &&
            item.meta?.category === undefined &&
            item.meta?.city === undefined &&
            item.meta?.location === undefined,
        ),
      ),
    ).toBe(true);

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(31, 'City filtered event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?city=Cluj&page=1&category=Technical', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    screen.getAllByRole('button', { name: /^All$/i }).forEach((button) => fireEvent.click(button));
    await waitFor(() =>
      expect(eventServiceMock.getEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: '' }),
      ),
    );
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(
      recordInteractionsSpy.mock.calls.some(([payload]) =>
        Array.isArray(payload) &&
        payload.some(
          (item: {
            interaction_type?: string;
            meta?: { category?: string; city?: string; location?: string };
          }) =>
            item?.interaction_type === 'filter' &&
            item.meta?.category === undefined &&
            item.meta?.city === 'Cluj' &&
            item.meta?.location === undefined,
        ),
      ),
    ).toBe(true);

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(31, 'Category selected event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);
    await waitFor(() =>
      expect(eventServiceMock.getEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: 'Technical' }),
      ),
    );

    cleanup();
    eventServiceMock.getEvents.mockResolvedValueOnce({
      items: [makeEvent(32, 'Date filtered event')],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
    renderLanguageRoute('/events?start_date=2026-03-10&page=1', '/events', <EventsPage />);
    await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
    expect(screen.getByText(/10 Mar 2026/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /10 Mar 2026/i }));
    fireEvent.click(
      requireElement(screen.queryByRole('button', { name: /Clear range/i }), 'clear range button'),
    );
  }, 20000);

  it('covers recommendation panel fallback and cleanup branches', async () => {
    let resolveRecommended:
      | ((value: { items: ReturnType<typeof makeEvent>[]; total: number; page: number; page_size: number; total_pages: number }) => void)
      | undefined;
    let rejectFavorites: ((reason?: unknown) => void) | undefined;

    eventServiceMock.getEvents.mockImplementation(async (filters: { sort?: string; page_size?: number }) => {
      if (filters?.sort === 'recommended' && filters?.page_size === 4) {
        return await new Promise((resolve) => {
          resolveRecommended = resolve as typeof resolveRecommended;
        });
      }
      return { items: [makeEvent(41, 'Cleanup event')], total: 1, page: 1, page_size: 12, total_pages: 1 };
    });
    eventServiceMock.getFavorites.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectFavorites = reject;
      }),
    );

    const pendingRender = renderLanguageRoute('/events', '/events', <EventsPage />);
    await screen.findByText(/Cleanup event/i);
    pendingRender.unmount();
    resolveRecommended?.({
      items: [makeEvent(91, 'Late recommended event')],
      total: 1,
      page: 1,
      page_size: 4,
      total_pages: 1,
    });
    rejectFavorites?.(new Error('late-favorites-fail'));
    await Promise.resolve();

    cleanup();
    eventServiceMock.getEvents.mockImplementation(async (filters: { sort?: string; page_size?: number }) => {
      if (filters?.sort === 'recommended' && filters?.page_size === 4) {
        throw new Error('recommended-panel-fail');
      }
      return { items: [makeEvent(42, 'Fallback event')], total: 1, page: 1, page_size: 12, total_pages: 1 };
    });
    eventServiceMock.getFavorites.mockRejectedValueOnce(new Error('favorites-panel-fail'));

    renderLanguageRoute('/events', '/events', <EventsPage />);
    await screen.findByText(/Fallback event/i);
    await waitFor(() => expect(eventServiceMock.getFavorites).toHaveBeenCalled());
    expect(screen.queryByText(/Late recommended event/i)).not.toBeInTheDocument();
  });
});
