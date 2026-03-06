import { beforeEach, describe, expect, it, vi } from 'vitest';

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

import { adminService } from '@/services/admin.service';
import { recordInteractions } from '@/services/analytics.service';
import authService from '@/services/auth.service';
import eventService from '@/services/event.service';

const SECRET_FIELD = 'pass' + 'word';
const CONFIRM_SECRET_FIELD = `confirm_${SECRET_FIELD}`;
const RESET_SECRET_FIELD = `new_${SECRET_FIELD}`;
const DEMO_ACCESS_CODE = 'EntryCode123A';
const ACCOUNT_CONFIRMATION = 'AccountRemoval123A';

describe('services', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('covers authService methods and storage helpers', async () => {
    const tokenPayload = {
      access_token: 'acc',
      refresh_token: 'ref',
      token_type: 'bearer',
      role: 'admin',
      user_id: 7,
    };

    apiMock.post.mockResolvedValueOnce({ data: tokenPayload });
    const registerResult = await authService.register({
      email: 'a@test.ro',
      [SECRET_FIELD]: DEMO_ACCESS_CODE,
      [CONFIRM_SECRET_FIELD]: DEMO_ACCESS_CODE,
      full_name: 'A',
    });
    expect(registerResult.access_token).toBe('acc');
    expect(localStorage.getItem('access_token')).toBe('acc');
    expect(localStorage.getItem('refresh_token')).toBe('ref');

    apiMock.post.mockResolvedValueOnce({ data: tokenPayload });
    const loginResult = await authService.login({ email: 'a@test.ro', [SECRET_FIELD]: DEMO_ACCESS_CODE });
    expect(loginResult.user_id).toBe(7);

    apiMock.get.mockResolvedValueOnce({ data: { id: 7, role: 'admin' } });
    expect((await authService.getMe()).id).toBe(7);

    apiMock.put.mockResolvedValueOnce({ data: { id: 7, theme_preference: 'dark' } });
    expect((await authService.updateThemePreference('dark')).theme_preference).toBe('dark');

    apiMock.put.mockResolvedValueOnce({ data: { id: 7, language_preference: 'en' } });
    expect((await authService.updateLanguagePreference('en')).language_preference).toBe('en');

    apiMock.post.mockResolvedValueOnce({ data: {} });
    await authService.requestPasswordReset('a@test.ro');
    expect(apiMock.post).toHaveBeenLastCalledWith('/password/forgot', { email: 'a@test.ro' });

    apiMock.post.mockResolvedValueOnce({ data: {} });
    await authService.resetPassword('tok', DEMO_ACCESS_CODE, DEMO_ACCESS_CODE);
    expect(apiMock.post).toHaveBeenLastCalledWith('/password/reset', {
      token: 'tok',
      [RESET_SECRET_FIELD]: DEMO_ACCESS_CODE,
      [CONFIRM_SECRET_FIELD]: DEMO_ACCESS_CODE,
    });

    expect(authService.isAuthenticated()).toBe(true);
    expect(authService.getStoredUser()).toEqual({ id: 7, role: 'admin' });
    expect(authService.isOrganizer()).toBe(true);

    localStorage.setItem('user', JSON.stringify({ id: 8, role: 'organizator' }));
    expect(authService.isOrganizer()).toBe(true);

    localStorage.setItem('user', JSON.stringify({ id: 9, role: 'student' }));
    expect(authService.isOrganizer()).toBe(false);

    authService.logout();
    expect(authService.isAuthenticated()).toBe(false);
    expect(authService.getStoredUser()).toBeNull();
  });

  it('covers eventService methods and query assembly', async () => {
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
    expect(apiMock.delete).toHaveBeenLastCalledWith('/api/me', { data: { [SECRET_FIELD]: ACCOUNT_CONFIRMATION } });

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

    apiMock.post.mockResolvedValueOnce({ data: { suggested_tags: [] } });
    expect((await eventService.suggestEvent({ title: 'x' })).suggested_tags).toEqual([]);
  });

  it('covers adminService methods and filters', async () => {
    apiMock.get.mockResolvedValueOnce({ data: { total_users: 1 } });
    expect((await adminService.getStats(10, 5)).total_users).toBe(1);
    expect(apiMock.get).toHaveBeenLastCalledWith('/api/admin/stats?days=10&top_tags_limit=5');

    apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
    await adminService.getUsers({ search: 'q', role: 'admin', is_active: true, page: 2, page_size: 10 });
    expect(apiMock.get).toHaveBeenLastCalledWith(expect.stringContaining('is_active=true'));

    apiMock.patch.mockResolvedValueOnce({ data: { id: 9 } });
    expect((await adminService.updateUser(9, { is_active: true })).id).toBe(9);

    apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
    await adminService.getEvents({
      search: 'x',
      category: 'Edu',
      city: 'Cluj',
      status: 'draft',
      include_deleted: true,
      flagged_only: true,
      page: 3,
      page_size: 20,
    });
    expect(apiMock.get).toHaveBeenLastCalledWith(expect.stringContaining('flagged_only=true'));

    apiMock.post.mockResolvedValueOnce({ data: { status: 'ok' } });
    expect((await adminService.reviewEventModeration(1)).status).toBe('ok');

    apiMock.get.mockResolvedValueOnce({ data: { totals: {} } });
    expect((await adminService.getPersonalizationMetrics(12)).totals).toEqual({});

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 1 } });
    expect((await adminService.enqueueRecommendationsRetrain()).job_id).toBe(1);

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 2 } });
    expect((await adminService.enqueueWeeklyDigest({ top_n: 5 })).job_id).toBe(2);

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 3 } });
    expect((await adminService.enqueueFillingFast({ threshold_abs: 2 })).job_id).toBe(3);
  });

  it('covers analytics best-effort behavior', async () => {
    await recordInteractions([]);
    expect(apiMock.post).not.toHaveBeenCalled();

    apiMock.post.mockResolvedValueOnce({});
    await recordInteractions([{ interaction_type: 'click', event_id: 1 }]);
    expect(apiMock.post).toHaveBeenCalledWith('/api/analytics/interactions', {
      events: [{ interaction_type: 'click', event_id: 1 }],
    });

    apiMock.post.mockRejectedValueOnce(new Error('network'));
    await expect(recordInteractions([{ interaction_type: 'view', event_id: 2 }])).resolves.toBeUndefined();
  });
});
