import { useEffect } from 'react';
import { act, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import { getHighImpactPageFixtures } from './high-impact-pages-coverage.fixtures';

const { authState, eventServiceMock } = getHighImpactPageFixtures();
const { useStudentProfileController } = await import('@/pages/profile/student-profile/useStudentProfileController');

/** Capture the loaded student-profile controller so guard methods can be exercised directly. */
function ControllerHarness({
  onReady,
}: Readonly<{ onReady: (controller: ReturnType<typeof useStudentProfileController>) => void }>) {
  const controller = useStudentProfileController();

  useEffect(() => {
    if (!controller.isLoading) {
      onReady(controller);
    }
  }, [controller, onReady]);

  return null;
}

it('covers student profile controller guards when personalization state is unavailable', async () => {
  authState.user = { id: 11, role: 'organizator', email: 'org@test.local' };
  const onReady = vi.fn();

  renderLanguageRoute('/profile', '/profile', <ControllerHarness onReady={onReady} />);
  await waitFor(() => expect(onReady).toHaveBeenCalled());

  const controller = onReady.mock.calls.at(-1)?.[0];
  expect(controller).toBeDefined();

  await act(async () => {
    controller.setDeletePassword('secret-access-code');
    controller.setDeleteDialogOpen(true);
    controller.setDeleteDialogOpen((previous) => !previous);
    await controller.handleNotificationPreferenceChange({ email_digest_enabled: true });
    await controller.handleUnhideTag(1);
    await controller.handleUnblockOrganizer(2);
  });

  expect(eventServiceMock.updateNotificationPreferences).not.toHaveBeenCalled();
  expect(eventServiceMock.unhideTag).not.toHaveBeenCalled();
  expect(eventServiceMock.unblockOrganizer).not.toHaveBeenCalled();
});
