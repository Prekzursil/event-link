import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  AdminDashboardPage,
  getMegaPagesSmokeFixtures,
} from './mega-pages-smoke.shared';

const { adminServiceMock } = getMegaPagesSmokeFixtures();

describe('mega pages admin smoke', () => {
  it('covers admin dashboard loading and tab-driven fetches', async () => {
    renderLanguageRoute('/admin', '/admin', <AdminDashboardPage />);

    await waitFor(() => expect(adminServiceMock.getStats).toHaveBeenCalled());
    await waitFor(() => expect(adminServiceMock.getPersonalizationMetrics).toHaveBeenCalled());

    const tabs = await screen.findAllByRole('tab');
    fireEvent.click(tabs[1]);
    fireEvent.click(tabs[2]);
    expect(tabs).toHaveLength(3);
  });
});
