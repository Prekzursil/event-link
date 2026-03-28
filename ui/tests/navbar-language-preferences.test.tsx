import { fireEvent, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  getEnabledButton,
  getLayoutUiFixtures,
} from './layout-and-ui-smoke.shared';
import { renderNavbar } from './navbar-smoke.helpers';

const { authServiceMock, authState, toastSpy } = getLayoutUiFixtures();

it('covers desktop language preference save success and failure paths', async () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = false;
  authState.isAdmin = false;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  authServiceMock.updateLanguagePreference.mockResolvedValueOnce(undefined);
  authServiceMock.updateLanguagePreference.mockRejectedValueOnce(new Error('lang-fail'));
  renderNavbar();

  fireEvent.mouseDown(getEnabledButton(/Language|Limba/i, 'enabled language trigger'));
  fireEvent.click(getEnabledButton(/Romanian|Română/i, 'enabled Romanian button'));
  await waitFor(() =>
    expect(authServiceMock.updateLanguagePreference.mock.calls.some(([value]) => value === 'ro')).toBe(true),
  );

  fireEvent.mouseDown(getEnabledButton(/Language|Limba/i, 'enabled language trigger after Romanian save'));
  fireEvent.click(getEnabledButton(/^English$/i, 'enabled English button'));
  await waitFor(() =>
    expect(authServiceMock.updateLanguagePreference.mock.calls.some(([value]) => value === 'en')).toBe(true),
  );
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
}, 15000);
