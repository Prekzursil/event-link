import React from 'react';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  EventsPage,
  getHighImpactPageFixtures,
  makeEvent,
} from './high-impact-pages-coverage.fixtures';

const {
  eventServiceMock,
  mediaAddEventListenerSpy,
  mediaAddListenerSpy,
  recordInteractionsSpy,
  toastSpy,
} = getHighImpactPageFixtures();

it('covers EventsPage filter and pagination handlers with favorite removal errors', async () => {
  renderLanguageRoute(
    '/events?search=abc&category=technical&city=Cluj&location=Hall&start_date=2026-03-01&end_date=2026-03-02&page=2&sort=recommended&page_size=12',
    '/events',
    <EventsPage />,
  );

  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
  expect(mediaAddEventListenerSpy.mock.calls.length + mediaAddListenerSpy.mock.calls.length).toBeGreaterThan(0);

  fireEvent.change(screen.getByPlaceholderText(/Search events/i), {
    target: { value: 'new query' },
  });
  fireEvent.change(screen.getByPlaceholderText(/City/i), { target: { value: 'Iasi' } });
  fireEvent.change(screen.getByPlaceholderText(/Location/i), { target: { value: 'Campus' } });

  fireEvent.click(screen.getByText(/Recommended for you/i));
  fireEvent.click(screen.getByText(/Soonest/i));

  await screen.findByTestId('event-1');
  fireEvent.click(screen.getByRole('button', { name: /toggle-favorite-1/i }));
  fireEvent.click(screen.getByRole('button', { name: /open-event-1/i }));
  fireEvent.click(screen.getByRole('button', { name: /Clear all/i }));
  await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

  cleanup();
  eventServiceMock.getEvents.mockResolvedValueOnce({
    items: [makeEvent(2)],
    total: 25,
    page: 2,
    page_size: 12,
    total_pages: 3,
  });
  eventServiceMock.getFavorites.mockResolvedValueOnce({ items: [makeEvent(2)] });
  eventServiceMock.removeFromFavorites.mockRejectedValueOnce(new Error('fav-remove-fail'));
  renderLanguageRoute('/events?page=2', '/events', <EventsPage />);
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

  const event2Card = await screen.findByTestId('event-2');
  fireEvent.click(within(event2Card).getByRole('button', { name: /toggle-favorite-2/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  const pager = requireElement(
    screen.getByText(/Page\s+2\s+of\s+3/i).parentElement,
    'events pager',
  );
  const pagerButtons = within(pager).getAllByRole('button');
  fireEvent.click(pagerButtons[0]);
  fireEvent.click(pagerButtons[1]);
}, 20000);

it('covers EventsPage recommendation clicks and search/filter interaction payloads', async () => {
  eventServiceMock.getEvents.mockImplementation(
    (filters: { sort?: string; page_size?: number }) => {
      if (filters?.sort === 'recommended' && filters?.page_size === 4) {
        return Promise.resolve({
          items: [makeEvent(90)],
          total: 1,
          page: 1,
          page_size: 4,
          total_pages: 1,
        });
      }
      return Promise.resolve({
        items: [makeEvent(1)],
        total: 25,
        page: 1,
        page_size: 12,
        total_pages: 3,
      });
    },
  );

  renderLanguageRoute(
    '/events?search=ai&category=technical&city=Cluj&location=Hall&tags=ai,ml&page=1',
    '/events',
    <EventsPage />,
  );
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

  await new Promise((resolve) => setTimeout(resolve, 450));
  await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

  fireEvent.click(screen.getByRole('button', { name: /^All$/i }));
  fireEvent.click(screen.getByRole('button', { name: /Select date range/i }));
  fireEvent.click(screen.getByRole('button', { name: /Pick range/i }));

  const activeFilterIcons = Array.from(document.querySelectorAll('svg.cursor-pointer'));
  expect(activeFilterIcons.length).toBeGreaterThan(1);
  fireEvent.click(requireElement(activeFilterIcons[1], 'category active filter icon'));

  Array.from(document.querySelectorAll('svg.cursor-pointer')).forEach((icon) => {
    fireEvent.click(icon);
  });

  cleanup();

  renderLanguageRoute('/events?tags=ai,ml&page=1', '/events', <EventsPage />);
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: /clear/i }));

  const pageSizeOption = screen
    .getAllByRole('button')
    .find((button) => (button.textContent || '').trim().startsWith('24'));
  fireEvent.click(requireElement(pageSizeOption, 'page size option'));

  cleanup();

  renderLanguageRoute('/events?category=technical&page=1', '/events', <EventsPage />);
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

  const categoryOnlyIcons = Array.from(document.querySelectorAll('svg.cursor-pointer'));
  if (categoryOnlyIcons.length) {
    fireEvent.click(requireElement(categoryOnlyIcons[0], 'category only icon'));
  }

  await new Promise((resolve) => setTimeout(resolve, 450));
  await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());

  const recommendationsPager = requireElement(
    screen.getByText(/Page\s+1\s+of\s+3/i).parentElement,
    'recommendations pager',
  );
  const pagerButtons = within(recommendationsPager).getAllByRole('button');
  fireEvent.click(pagerButtons[1]);

  cleanup();

  renderLanguageRoute('/events?sort=time', '/events', <EventsPage />);
  await waitFor(() => expect(eventServiceMock.getEvents).toHaveBeenCalled());

  const recommendationsHeading = await screen.findByRole('heading', {
    name: /Recommended for you/i,
  });
  const recommendationsSection = recommendationsHeading.closest('div')?.parentElement;
  fireEvent.click(
    within(requireElement(recommendationsSection, 'recommendations section')).getByRole(
      'button',
      { name: /open-event-90/i },
    ),
  );
  await waitFor(() =>
    expect(recordInteractionsSpy).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          interaction_type: 'click',
          meta: expect.objectContaining({ source: 'recommendations_grid' }),
        }),
      ]),
    ),
  );
}, 20000);
