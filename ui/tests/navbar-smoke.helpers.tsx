import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import {
  LanguageProvider,
  Navbar,
  ThemeProvider,
  requireValue,
} from './layout-and-ui-smoke.shared';

/**
 * Renders the navbar scaffolding for tests.
 */
export function renderNavbar() {
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

/**
 * Opens the mobile navbar menu UI surface for tests.
 */
export function openMobileNavbarMenu(label: string) {
  const menuButton = requireValue(
    screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
    label,
  );
  fireEvent.click(menuButton);
  return menuButton;
}
