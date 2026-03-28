import { fireEvent, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import {
  getEnabledButton,
  getLayoutUiFixtures,
} from './layout-and-ui-smoke.shared';
import { renderNavbar } from './navbar-smoke.helpers';

const { authServiceMock } = getLayoutUiFixtures();

it('keeps guest preference changes local without persisting through the auth service', async () => {
  renderNavbar();

  fireEvent.mouseDown(getEnabledButton(/Theme|Tema/i, 'guest theme trigger'));
  fireEvent.click(getEnabledButton(/Dark|Întunecat/i, 'guest dark option'));
  await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true));
  expect(authServiceMock.updateThemePreference).not.toHaveBeenCalled();

  fireEvent.mouseDown(getEnabledButton(/Language|Limba/i, 'guest language trigger'));
  fireEvent.click(getEnabledButton(/Romanian|Română/i, 'guest Romanian option'));
  await waitFor(() => expect(document.documentElement.lang).toBe('ro'));
  expect(authServiceMock.updateLanguagePreference).not.toHaveBeenCalled();
});
