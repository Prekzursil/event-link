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

import { adminService } from '@/services/admin.service';

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

it('covers stats and user-management routes', async () => {
  apiMock.get.mockResolvedValueOnce({ data: { total_users: 1 } });
  expect((await adminService.getStats(10, 5)).total_users).toBe(1);
  expect(apiMock.get).toHaveBeenLastCalledWith('/api/admin/stats?days=10&top_tags_limit=5');

    apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
    await adminService.getUsers();
    expect(apiMock.get).toHaveBeenLastCalledWith('/api/admin/users?');

    apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
    await adminService.getUsers({ search: 'q', role: 'admin', is_active: true, page: 2, page_size: 10 });
    expect(apiMock.get).toHaveBeenLastCalledWith(expect.stringContaining('is_active=true'));

  apiMock.patch.mockResolvedValueOnce({ data: { id: 9 } });
  expect((await adminService.updateUser(9, { is_active: true })).id).toBe(9);
});

it('covers event moderation and personalization routes', async () => {
  apiMock.get.mockResolvedValueOnce({ data: { items: [] } });
  await adminService.getEvents();
  expect(apiMock.get).toHaveBeenLastCalledWith('/api/admin/events?');

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
});

it('covers retrain and notification enqueue routes', async () => {
  apiMock.post.mockResolvedValueOnce({ data: { job_id: 1 } });
  expect((await adminService.enqueueRecommendationsRetrain()).job_id).toBe(1);

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 2 } });
    expect((await adminService.enqueueWeeklyDigest({ top_n: 5 })).job_id).toBe(2);

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 3 } });
    expect((await adminService.enqueueFillingFast({ threshold_abs: 2 })).job_id).toBe(3);

    apiMock.post.mockResolvedValueOnce({ data: { job_id: 4 } });
    expect((await adminService.enqueueWeeklyDigest()).job_id).toBe(4);
    expect(apiMock.post).toHaveBeenLastCalledWith('/api/admin/notifications/weekly-digest', {});

  apiMock.post.mockResolvedValueOnce({ data: { job_id: 5 } });
  expect((await adminService.enqueueFillingFast()).job_id).toBe(5);
  expect(apiMock.post).toHaveBeenLastCalledWith('/api/admin/notifications/filling-fast', {});
});
