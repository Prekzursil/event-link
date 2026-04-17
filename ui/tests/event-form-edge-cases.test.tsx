import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventFormPage,
  getEventPagesFixtures,
  makeEvent,
  requireForm,
} from './events-form-and-events-page.shared';

const { eventServiceMock, toastSpy } = getEventPagesFixtures();

describe('event form edge cases', () => {
  it('covers sparse edit defaults and suggestion fallback rendering', async () => {
    eventServiceMock.getEvent.mockResolvedValueOnce({
      ...makeEvent(44, 'Sparse event'),
      description: undefined,
      category: undefined,
      end_time: undefined,
      city: undefined,
      location: undefined,
      max_seats: undefined,
      cover_url: undefined,
      status: undefined,
      tags: [],
    });

    renderLanguageRoute('/organizer/events/44/edit', '/organizer/events/:id/edit', <EventFormPage />);
    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(44));
    expect(screen.getByLabelText(/Description/i)).toHaveValue('');
    expect(screen.getByLabelText(/City/iu)).toHaveValue('');
    expect(screen.getByLabelText(/Location/i)).toHaveValue('');
    expect(screen.getByLabelText(/Max seats/iu)).toHaveValue(null);

    cleanup();
    eventServiceMock.suggestEvent.mockResolvedValueOnce({
      suggested_category: '',
      suggested_city: '',
      suggested_tags: [],
      duplicates: [
        {
          id: 201,
          title: 'Possible duplicate',
          start_time: new Date().toISOString(),
          city: '',
          similarity: 0.33,
        },
      ],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);
    fireEvent.change(screen.getByLabelText(/Title/iu), { target: { value: 'Fallback event' } });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/iu }));
    await waitFor(() => expect(eventServiceMock.suggestEvent).toHaveBeenCalled());
    expect(screen.getAllByText('—').length).toBeGreaterThan(1);
    expect(screen.getByText(/- • 33%/iu)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/iu }));
    expect(screen.getByLabelText(/City/iu)).toHaveValue('');

    const tagInput = screen.getByPlaceholderText(/tag/iu);
    fireEvent.keyDown(tagInput, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/iu }));
    expect(screen.queryByText(/^AI$/iu)).not.toBeInTheDocument();

    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/iu }));
    fireEvent.change(tagInput, { target: { value: 'AI' } });
    fireEvent.click(screen.getByRole('button', { name: /^Add$/iu }));
    expect(screen.getAllByText('AI')).toHaveLength(1);

    fireEvent.change(screen.getByLabelText(/Max seats/iu), { target: { value: '' } });
    expect(screen.getByLabelText(/Max seats/iu)).toHaveValue(null);
  });

  it('covers suggest payload timestamps, duplicate-apply retention, and max-seats reset', async () => {
    let resolveSuggestion:
      | ((value: Awaited<ReturnType<typeof eventServiceMock.suggestEvent>>) => void)
      | undefined;
    eventServiceMock.suggestEvent.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSuggestion = resolve as (
          value: Awaited<ReturnType<typeof eventServiceMock.suggestEvent>>,
        ) => void;
      }),
    );

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/iu), {
      target: { value: 'Suggest payload event' },
    });
    fireEvent.change(screen.getByLabelText(/City/iu), { target: { value: 'Braila' } });
    fireEvent.change(screen.getByLabelText(/Start date/iu), {
      target: { value: '2026-03-10T10:00' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);

    fireEvent.click(screen.getByRole('button', { name: /Suggest/iu }));
    await waitFor(() =>
      expect(eventServiceMock.suggestEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Suggest payload event',
          city: 'Braila',
          start_time: new Date('2026-03-10T10:00').toISOString(),
        }),
      ),
    );

    resolveSuggestion?.({
      suggested_category: 'Social',
      suggested_city: 'Iasi',
      suggested_tags: ['AI'],
      duplicates: [],
      moderation_score: 0,
      moderation_flags: [],
      moderation_status: 'clear',
    });
    fireEvent.click(await screen.findByRole('button', { name: /^Apply$/iu }));

    expect(screen.getByLabelText(/City/iu)).toHaveValue('Braila');
    expect(screen.getAllByText('AI').length).toBeGreaterThan(0);

    const maxSeatsInput = screen.getByLabelText(/Max seats/iu);
    fireEvent.change(maxSeatsInput, { target: { value: '12' } });
    fireEvent.change(maxSeatsInput, { target: { value: '' } });
    expect(maxSeatsInput).toHaveValue(null);

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Hall A' } });
    fireEvent.change(maxSeatsInput, { target: { value: '24' } });
    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() =>
      expect(eventServiceMock.createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          category: 'Technical',
          city: 'Braila',
          max_seats: 24,
        }),
      ),
    );
  }, 20000);

  it('covers generic suggestion and submit fallback errors', async () => {
    eventServiceMock.suggestEvent.mockRejectedValueOnce(new Error('plain-suggest-error'));
    eventServiceMock.createEvent.mockRejectedValueOnce(new Error('plain-create-error'));

    renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

    fireEvent.change(screen.getByLabelText(/Title/iu), {
      target: { value: 'Fallback create event' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Suggest/iu }));
    await waitFor(() =>
      expect(eventServiceMock.suggestEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Fallback create event',
          description: undefined,
          city: undefined,
          location: undefined,
          start_time: undefined,
        }),
      ),
    );
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.click(screen.getAllByRole('button', { name: /Technical|Tehnic/i })[0]);
    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Aula Magna' } });
    fireEvent.change(screen.getByLabelText(/City/iu), { target: { value: 'Cluj' } });
    fireEvent.change(screen.getByLabelText(/Start date/iu), {
      target: { value: '2026-03-10T10:00' },
    });
    fireEvent.change(screen.getByLabelText(/Max seats/iu), { target: { value: '25' } });

    fireEvent.submit(requireForm(/Create event/i, screen));
    await waitFor(() => expect(eventServiceMock.createEvent).toHaveBeenCalled());
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });
});
