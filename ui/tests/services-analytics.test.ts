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

import { recordInteractions } from '@/services/analytics.service';

function resetServiceMocks() {
  vi.clearAllMocks();
  localStorage.clear();
}

describe('analytics service', () => {
  beforeEach(() => {
    resetServiceMocks();
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
