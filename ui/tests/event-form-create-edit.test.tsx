import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventFormPage,
  getEventPagesFixtures,
  requireForm,
} from './events-form-and-events-page.shared';

const { eventServiceMock, navigateSpy, toastSpy } = getEventPagesFixtures();

describe('event form create and edit flows', () => {
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

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateEvent).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');

    eventServiceMock.getEvent.mockRejectedValueOnce(new Error('load-failed'));
    renderLanguageRoute('/organizer/events/88/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/organizer'));
  });

  it('covers validation branches, suggest-error detail, and tag/image helpers', async () => {
    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: 'Validation Event' } });
    fireEvent.change(screen.getByLabelText(/Description/i), {
      target: { value: 'Validation description' },
    });

    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.suggestEvent.mockRejectedValueOnce({
      response: { data: { detail: 'bad-suggest' } },
    });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    eventServiceMock.suggestEvent.mockResolvedValueOnce({
      suggested_category: 'Technical',
      suggested_city: 'Cluj',
      suggested_tags: ['A'],
      duplicates: [],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/i }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/i }));

    screen
      .getAllByRole('button', { name: /Technical|Tehnic/i })
      .forEach((button) => fireEvent.click(button));
    screen
      .getAllByRole('button', { name: /Draft|Ciornă/i })
      .forEach((button) => fireEvent.click(button));

    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: '' } });
    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj' } });
    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Start date/i), {
      target: { value: '2026-03-10T10:00' },
    });
    fireEvent.change(screen.getByLabelText(/End date/i), {
      target: { value: '2026-03-10T12:00' },
    });
    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Max seats/i), { target: { value: '20' } });

    const coverInput = document.getElementById('cover_url');
    expect(coverInput).not.toBeNull();
    fireEvent.change(coverInput, { target: { value: 'https://example.com/img.jpg' } });
    const preview = screen.getByAltText(/Preview/i);
    fireEvent.error(preview);
    expect(preview.style.display).toBe('none');

    const addTagButton = screen.getByRole('button', { name: /Add/i });
    const tagInput = screen.getByPlaceholderText(/tag/i);
    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(addTagButton);
    expect(screen.getByText('AI')).toBeInTheDocument();

    const removeIcon = document.querySelector('svg.h-3.w-3.cursor-pointer');
    expect(removeIcon).not.toBeNull();
    fireEvent.click(removeIcon!);

    eventServiceMock.createEvent.mockRejectedValueOnce({
      response: { data: { detail: 'create-fail' } },
    });
    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(tagInput, { target: { value: 'ML' } });
    fireEvent.keyDown(tagInput, { key: 'Enter' });

    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
  }, 20000);

  it('covers back and cancel navigation actions', async () => {
    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.click(screen.getByRole('button', { name: /Back/i }));
    expect(navigateSpy).toHaveBeenCalledWith(-1);

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(navigateSpy).toHaveBeenCalledWith('/organizer');
  });
});
