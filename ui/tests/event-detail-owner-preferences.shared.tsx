import { renderLanguageRoute } from './page-test-helpers';
import { EventDetailPage } from './event-detail-branches.shared';

export function renderEventDetail(path = '/events/1') {
  return renderLanguageRoute(path, '/events/:id', <EventDetailPage />);
}

export function makeEvent(overrides?: Partial<Record<string, unknown>>) {
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
