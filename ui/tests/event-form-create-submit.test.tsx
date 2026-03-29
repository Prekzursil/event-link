import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventFormPage,
  getEventPagesFixtures,
  requireForm,
} from './events-form-and-events-page.shared';

const { eventServiceMock, navigateSpy, toastSpy } = getEventPagesFixtures();

it('covers create flow with suggest, apply, and final submit', async () => {
  renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

  fireEvent.submit(requireForm(/Create event/i, screen));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'AI Meetup' } });
  fireEvent.change(screen.getByLabelText(/Description/i), {
    target: { value: 'A meetup about AI' },
  });
  fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
  await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());

  fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));

  fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
  fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
  fireEvent.change(screen.getByLabelText(/Start date/i), {
    target: { value: '2026-03-10T10:00' },
  });
  fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '100' } });

  fireEvent.click(screen.getByRole('button', { name: /Create event/i }));
  await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
  expect(navigateSpy).toHaveBeenCalledWith('/events/77');
});

it('covers edit load and update success plus the load-failure redirect', async () => {
  renderLanguageRoute('/organizer/events/33/edit', '/organizer/events/:id/edit', <EventFormPage />);
  await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(33));

  fireEvent.click(await screen.findByRole('button', { name: /Save changes/i }));
  await waitFor(() => expect(eventServiceMock.updateEvent).toHaveBeenCalled());
  expect(navigateSpy).toHaveBeenCalledWith('/organizer');

  navigateSpy.mockClear();
  eventServiceMock.getEvent.mockRejectedValueOnce(new Error('load-failed'));
  renderLanguageRoute('/organizer/events/88/edit', '/organizer/events/:id/edit', <EventFormPage />);
  await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/organizer'));
});
