import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import {
  LanguageProvider,
  Navbar,
  ThemeProvider,
  requireValue,
} from './layout-and-ui-smoke.shared';

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

export function openMobileNavbarMenu(label: string) {
  const menuButton = requireValue(
    screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
    label,
  );
  fireEvent.click(menuButton);
  return menuButton;
}
