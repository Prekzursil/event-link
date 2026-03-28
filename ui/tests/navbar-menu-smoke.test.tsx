import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it } from 'vitest';

import {
  LanguageProvider,
  Navbar,
  ThemeProvider,
  getLayoutUiFixtures,
  requireValue,
} from './layout-and-ui-smoke.shared';

const { authState, authServiceMock } = getLayoutUiFixtures();

function renderNavbar() {
  render(
    <MemoryRouter>
      <ThemeProvider>
        <LanguageProvider>
          <Navbar />
        </LanguageProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

it('renders the guest navbar and opens the mobile menu', async () => {
  renderNavbar();

  expect(screen.getByText(/EventLink/i)).toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);
  expect(screen.getAllByRole('link', { name: /Register/i }).length).toBeGreaterThan(0);

  const menuButton = requireValue(
    screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
    'guest mobile menu button',
  );
  fireEvent.click(menuButton);

  expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);

  const loginLink = requireValue(
    screen
      .getAllByRole('link', { name: /Log in/i })
      .find((link) => link.className.includes('w-full')),
    'guest login link',
  );
  fireEvent.click(loginLink);

  fireEvent.click(
    requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'guest mobile menu button after login click',
    ),
  );
  const registerLink = requireValue(
    screen
      .getAllByRole('link', { name: /Register/i })
      .find((link) => link.className.includes('w-full')),
    'guest register link',
  );
  fireEvent.click(registerLink);
}, 15000);

it('renders the authenticated navbar and triggers logout from the mobile menu', () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  renderNavbar();

  expect(screen.getAllByRole('link', { name: /Dashboard/i }).length).toBeGreaterThan(0);

  const menuButton = requireValue(
    screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
    'authenticated mobile menu button',
  );
  fireEvent.click(menuButton);

  fireEvent.click(screen.getAllByRole('button', { name: /Log out/i })[0]);
  expect(authState.logout).toHaveBeenCalled();
});

it('covers navbar system selectors and mobile link close handlers', async () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  renderNavbar();

  const menuButton = requireValue(
    screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
    'authenticated mobile menu button',
  );
  fireEvent.click(menuButton);

  const systemButtons = screen.getAllByRole('button', { name: /System|Sistem/i });
  systemButtons.forEach((button) => fireEvent.click(button));

  const lightButtons = screen.getAllByRole('button', { name: /Light|Luminos/i });
  const darkButtons = screen.getAllByRole('button', { name: /Dark|Întunecat/i });
  fireEvent.click(lightButtons[lightButtons.length - 1]);
  fireEvent.click(darkButtons[darkButtons.length - 1]);

  const roButtons = screen.getAllByRole('button', { name: /Romanian|Română/i });
  const enButtons = screen.getAllByRole('button', { name: /^English$/i });
  roButtons.forEach((button) => fireEvent.click(button));
  enButtons.forEach((button) => fireEvent.click(button));
  await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalled());

  const dashboardLink = requireValue(
    screen
      .getAllByRole('link', { name: /Dashboard/i })
      .find((link) => link.className.includes('rounded-md')),
    'dashboard link',
  );
  fireEvent.click(dashboardLink);

  const newEventLinks = screen.getAllByRole('link', { name: /New event|Event nou/i });
  expect(newEventLinks.length).toBeGreaterThan(0);
  fireEvent.click(newEventLinks[newEventLinks.length - 1]);

  const logoutButtons = screen.getAllByRole('button', { name: /Log out/i });
  fireEvent.click(logoutButtons[logoutButtons.length - 1]);
  expect(authState.logout).toHaveBeenCalled();
}, 20000);
