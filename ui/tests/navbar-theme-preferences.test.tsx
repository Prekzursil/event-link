import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  getEnabledButton,
  getLayoutUiFixtures,
} from './layout-and-ui-smoke.shared';
import { renderNavbar } from './navbar-smoke.helpers';

const { authServiceMock, authState, toastSpy } = getLayoutUiFixtures();

it('covers desktop theme preference save success and failure paths', async () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = false;
  authState.isAdmin = false;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  authServiceMock.updateThemePreference.mockResolvedValueOnce(undefined);
  authServiceMock.updateThemePreference.mockRejectedValueOnce(new Error('theme-fail'));
  renderNavbar();

  fireEvent.mouseDown(getEnabledButton(/Theme|Tema/i, 'enabled theme trigger'));
  fireEvent.click(getEnabledButton(/Light|Luminos/i, 'enabled light button'));
  await waitFor(() =>
    expect(authServiceMock.updateThemePreference.mock.calls.some(([value]) => value === 'light')).toBe(true),
  );

  await waitFor(() =>
    expect(screen.getAllByRole('button', { name: /Theme|Tema/i }).some((button) => !button.hasAttribute('disabled'))).toBe(true),
  );
  fireEvent.mouseDown(getEnabledButton(/Theme|Tema/i, 'enabled theme trigger after light save'));
  fireEvent.click(getEnabledButton(/Dark|Întunecat/i, 'enabled dark button'));
  await waitFor(() =>
    expect(authServiceMock.updateThemePreference.mock.calls.some(([value]) => value === 'dark')).toBe(true),
  );
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 15000);
