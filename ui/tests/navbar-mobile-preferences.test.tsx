import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it } from 'vitest';

import {
  LanguageProvider,
  Navbar,
  ThemeProvider,
  getLayoutUiFixtures,
  requireValue,
} from './layout-and-ui-smoke.shared';
import { renderNavbar } from './navbar-smoke.helpers';

const { authServiceMock, authState, toastSpy } = getLayoutUiFixtures();

it('covers mobile dropdown option branches explicitly', async () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

  renderNavbar();
  fireEvent.click(
    requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'guest mobile menu button',
    ),
  );

  const mobilePanel = requireValue(
    Array.from(document.querySelectorAll('div')).find((node) => {
      const className = typeof node.className === 'string' ? node.className : '';
      return className.includes('top-16') && className.includes('md:hidden');
    }),
    'mobile panel',
  );

  within(mobilePanel).getAllByRole('button', { name: /System|Sistem/i }).forEach((button) => fireEvent.click(button));
  within(mobilePanel).getAllByRole('button', { name: /Light|Luminos/i }).forEach((button) => fireEvent.click(button));
  within(mobilePanel).getAllByRole('button', { name: /Dark|Întunecat/i }).forEach((button) => fireEvent.click(button));
  within(mobilePanel).getAllByRole('button', { name: /Romanian|Română/i }).forEach((button) => fireEvent.click(button));
  within(mobilePanel).getAllByRole('button', { name: /^English$/i }).forEach((button) => fireEvent.click(button));

  await waitFor(() => expect(authServiceMock.updateThemePreference).toHaveBeenCalled());
  await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalled());
}, 20000);

it('covers initials fallback branches in the avatar', () => {
  authState.isAuthenticated = true;
  authState.isOrganizer = false;
  authState.isAdmin = false;
  authState.user = { full_name: null, email: 'beatrice@test.local', role: 'student' };

  const { rerender } = render(
    <MemoryRouter>
      <ThemeProvider>
        <LanguageProvider>
          <Navbar />
        </LanguageProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
  expect(screen.getByText('BE')).toBeInTheDocument();

  authState.user = { full_name: null, email: undefined, role: 'student' };
  rerender(
    <MemoryRouter>
      <ThemeProvider>
        <LanguageProvider>
          <Navbar />
        </LanguageProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
  expect(screen.getByText('U')).toBeInTheDocument();
  expect(toastSpy).not.toHaveBeenCalled();
});
