import { fireEvent, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import { requireValue } from './layout-and-ui-smoke.shared';
import {
  openMobileNavbarMenu,
  renderNavbar,
} from './navbar-smoke.helpers';

it('renders the guest navbar and opens the mobile menu', async () => {
  renderNavbar();

  expect(screen.getByText(/EventLink/i)).toBeInTheDocument();
  expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);
  expect(screen.getAllByRole('link', { name: /Register/i }).length).toBeGreaterThan(0);

  openMobileNavbarMenu('guest mobile menu button');
  expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);

  const loginLink = requireValue(
    screen.getAllByRole('link', { name: /Log in/i }).find((link) => link.className.includes('w-full')),
    'guest login link',
  );
  fireEvent.click(loginLink);

  openMobileNavbarMenu('guest mobile menu button after login click');
  const registerLink = requireValue(
    screen.getAllByRole('link', { name: /Register/i }).find((link) => link.className.includes('w-full')),
    'guest register link',
  );
  fireEvent.click(registerLink);
}, 15000);
