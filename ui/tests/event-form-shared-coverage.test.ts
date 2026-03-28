import { describe, expect, it } from 'vitest';
import { eventToFormState } from '@/pages/organizer/event-form/shared';

describe('event form shared coverage', () => {
  it('keeps draft status when converting an event into form state', () => {
    expect(
      eventToFormState({
        id: 1,
        title: 'Draft event',
        description: null,
        category: null,
        start_time: '2030-01-01T10:00:00Z',
        end_time: null,
        city: null,
        location: null,
        max_seats: null,
        cover_url: null,
        tags: [],
        status: 'draft',
      } as never).status,
    ).toBe('draft');
  });
});
