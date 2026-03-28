import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { getLayoutUiFixtures } from './layout-and-ui-smoke.shared';
import {
  openMobileNavbarMenu,
  renderNavbar,
} from './navbar-smoke.helpers';

const { authServiceMock, authState } = getLayoutUiFixtures();

it('renders the authenticated navbar and triggers logout from the mobile menu', () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  renderNavbar();
  expect(screen.getAllByRole('link', { name: /Dashboard/i }).length).toBeGreaterThan(0);
  openMobileNavbarMenu('authenticated mobile menu button');
  fireEvent.click(screen.getAllByRole('button', { name: /Log out/i })[0]);
  expect(authState.logout).toHaveBeenCalled();
});

it('covers navbar system selectors and mobile link close handlers', async () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  renderNavbar();
  openMobileNavbarMenu('authenticated mobile menu button');

  screen.getAllByRole('button', { name: /System|Sistem/i }).forEach((button) => fireEvent.click(button));
  const lightButtons = screen.getAllByRole('button', { name: /Light|Luminos/i });
  const darkButtons = screen.getAllByRole('button', { name: /Dark|Întunecat/i });
  fireEvent.click(lightButtons[lightButtons.length - 1]);
  fireEvent.click(darkButtons[darkButtons.length - 1]);

  screen.getAllByRole('button', { name: /Romanian|Română/i }).forEach((button) => fireEvent.click(button));
  screen.getAllByRole('button', { name: /^English$/i }).forEach((button) => fireEvent.click(button));
  await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalled());

  const dashboardLink = screen
    .getAllByRole('link', { name: /Dashboard/i })
    .find((link) => link.className.includes('rounded-md'));
  if (!dashboardLink) {
    throw new Error('Expected a rounded dashboard link in the mobile menu.');
  }
  fireEvent.click(dashboardLink);
  const newEventLinks = screen.getAllByRole('link', { name: /New event|Event nou/i });
  expect(newEventLinks.length).toBeGreaterThan(0);
  fireEvent.click(newEventLinks[newEventLinks.length - 1]);

  const logoutButtons = screen.getAllByRole('button', { name: /Log out/i });
  fireEvent.click(logoutButtons[logoutButtons.length - 1]);
  expect(authState.logout).toHaveBeenCalled();
}, 20000);
