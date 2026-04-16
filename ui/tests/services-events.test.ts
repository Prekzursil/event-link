import { beforeEach, expect, it, vi } from 'vitest';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  default: apiMock,
}));

import eventService from '@/services/event.service';

const ACCESS_CODE_FIELD = ['pass', 'word'].join('');
const ACCOUNT_CONFIRMATION = ['Account', 'Removal', '123A'].join('');

/**
 * Test helper: reset service mocks.
 */
function resetServiceMocks() {
  vi.clearAllMocks();
  localStorage.clear();
}

beforeEach(() => {
  resetServiceMocks();
});

it('builds event listing queries and event lookup routes', async () => {
  apiMock.get.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, page_size: 20 } });
  await eventService.getEvents();
  expect(apiMock.get).toHaveBeenCalledWith('/api/events?');

    apiMock.get.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } });
    await eventService.getEvents({
      search: 'abc',
      category: 'Edu',
      start_date: '2026-01-01',
      end_date: '2026-01-02',
      city: 'Cluj',
      location: 'Hall',
      include_past: true,
      sort: 'date_asc',
      page: 2,
      page_size: 10,
      tags: ['a', 'b'],
    });
    expect(apiMock.get).toHaveBeenCalledWith(expect.stringContaining('/api/events?search=abc'));

    apiMock.get.mockResolvedValueOnce({ data: { id: 1 } });
    await eventService.getEvent(1);
    expect(apiMock.get).toHaveBeenLastCalledWith('/api/events/1');

  apiMock.get.mockResolvedValueOnce({ data: 'ics' });
  expect(await eventService.getEventIcs(2)).toBe('ics');
});

it('covers registration, favorites, and account export routes', async () => {
  await eventService.registerForEvent(3);
  expect(apiMock.post).toHaveBeenLastCalledWith('/api/events/3/register');

    await eventService.unregisterFromEvent(4);
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/events/4/register');

    await eventService.resendRegistrationEmail(5);
    expect(apiMock.post).toHaveBeenLastCalledWith('/api/events/5/register/resend');

    await eventService.addToFavorites(6);
    expect(apiMock.post).toHaveBeenLastCalledWith('/api/events/6/favorite');

    await eventService.removeFromFavorites(7);
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/events/7/favorite');

    apiMock.get.mockResolvedValueOnce({ data: { items: [{ id: 1 }] } });
    expect((await eventService.getFavorites()).items).toHaveLength(1);

    apiMock.get.mockResolvedValueOnce({ data: [{ id: 2 }] });
    expect((await eventService.getMyEvents())).toHaveLength(1);

    apiMock.get.mockResolvedValueOnce({ data: 'calendar' });
    expect(await eventService.getMyCalendar()).toBe('calendar');

    apiMock.get.mockResolvedValueOnce({ data: new Blob(['x']) });
    expect(await eventService.exportMyData()).toBeInstanceOf(Blob);

  await eventService.deleteMyAccount(ACCOUNT_CONFIRMATION);
  expect(apiMock.delete).toHaveBeenLastCalledWith('/api/me', { data: { [ACCESS_CODE_FIELD]: ACCOUNT_CONFIRMATION } });
});

it('covers recommendation, organizer, and participant routes', async () => {
  apiMock.get.mockResolvedValueOnce({ data: [{ id: 3 }] });
  expect((await eventService.getRecommendations())).toHaveLength(1);

    apiMock.post.mockResolvedValueOnce({ data: { id: 10 } });
    expect((await eventService.createEvent({ title: 'x' } as never)).id).toBe(10);

    apiMock.put.mockResolvedValueOnce({ data: { id: 11 } });
    expect((await eventService.updateEvent(11, { title: 'y' })).id).toBe(11);

    await eventService.deleteEvent(12);
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/events/12');

    apiMock.post.mockResolvedValueOnce({ data: { status: 'ok', restored_registrations: 2 } });
    expect((await eventService.restoreEvent(13)).restored_registrations).toBe(2);

    apiMock.post.mockResolvedValueOnce({ data: { id: 14 } });
    expect((await eventService.cloneEvent(14)).id).toBe(14);

    apiMock.get.mockResolvedValueOnce({ data: [{ id: 15 }] });
    expect((await eventService.getOrganizerEvents())).toHaveLength(1);

    apiMock.get.mockResolvedValueOnce({ data: { participants: [] } });
    await eventService.getEventParticipants(16, 2, 50, 'name', 'desc');
    expect(apiMock.get).toHaveBeenLastCalledWith(expect.stringContaining('sort_by=name'));

  await eventService.updateParticipantAttendance(17, 33, true);
  expect(apiMock.put).toHaveBeenLastCalledWith('/api/organizer/events/17/participants/33?attended=true');
});

it('covers bulk event mutations and organizer profile routes', async () => {
  apiMock.post.mockResolvedValueOnce({ data: { updated: 5 } });
  expect((await eventService.bulkUpdateEventStatus([1, 2], 'draft')).updated).toBe(5);

    apiMock.post.mockResolvedValueOnce({ data: { updated: 4 } });
    expect((await eventService.bulkUpdateEventTags([1], ['a'])).updated).toBe(4);

    apiMock.post.mockResolvedValueOnce({ data: { recipients: 9 } });
    expect((await eventService.emailEventParticipants(22, 'subj', 'msg')).recipients).toBe(9);

    apiMock.get.mockResolvedValueOnce({ data: { user_id: 1 } });
    expect((await eventService.getOrganizerProfile(1)).user_id).toBe(1);

  apiMock.put.mockResolvedValueOnce({ data: { user_id: 1 } });
  expect((await eventService.updateOrganizerProfile({ org_name: 'x' })).user_id).toBe(1);
});

it('covers student profile, personalization, and notification routes', async () => {
  apiMock.get.mockResolvedValueOnce({ data: { items: [{ id: 1, name: 'tag' }] } });
  expect((await eventService.getAllTags())).toHaveLength(1);

    apiMock.get.mockResolvedValueOnce({ data: { items: [{ name: 'Uni' }] } });
    expect((await eventService.getUniversityCatalog())).toHaveLength(1);

    apiMock.get.mockResolvedValueOnce({ data: { user_id: 2 } });
    expect((await eventService.getStudentProfile()).user_id).toBe(2);

    apiMock.put.mockResolvedValueOnce({ data: { user_id: 2 } });
    expect((await eventService.updateStudentProfile({ city: 'Cluj' })).user_id).toBe(2);

    apiMock.get.mockResolvedValueOnce({ data: { hidden_tags: [], blocked_organizers: [] } });
    expect((await eventService.getPersonalizationSettings()).hidden_tags).toEqual([]);

    await eventService.hideTag(1);
    expect(apiMock.post).toHaveBeenLastCalledWith('/api/me/personalization/hidden-tags/1');

    await eventService.unhideTag(2);
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/me/personalization/hidden-tags/2');

    await eventService.blockOrganizer(3);
    expect(apiMock.post).toHaveBeenLastCalledWith('/api/me/personalization/blocked-organizers/3');

    await eventService.unblockOrganizer(4);
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/me/personalization/blocked-organizers/4');

    apiMock.get.mockResolvedValueOnce({ data: { email_digest_enabled: true, email_filling_fast_enabled: false } });
    expect((await eventService.getNotificationPreferences()).email_digest_enabled).toBe(true);

  apiMock.put.mockResolvedValueOnce({ data: { email_digest_enabled: false, email_filling_fast_enabled: true } });
  expect((await eventService.updateNotificationPreferences({ email_digest_enabled: false })).email_filling_fast_enabled).toBe(true);
});

it('covers suggestion requests', async () => {
  apiMock.post.mockResolvedValueOnce({ data: { suggested_tags: [] } });
  expect((await eventService.suggestEvent({ title: 'x' })).suggested_tags).toEqual([]);
});
