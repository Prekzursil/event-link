import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import {
  LanguageProvider,
  Navbar,
  ThemeProvider,
  getEnabledButton,
  getLayoutUiFixtures,
  requireValue,
} from './layout-and-ui-smoke.shared';

const { authServiceMock, authState, toastSpy } = getLayoutUiFixtures();

describe('navbar preference smoke', () => {
  it('keeps guest preference changes local without persisting through the auth service', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <LanguageProvider>
            <Navbar />
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    fireEvent.mouseDown(getEnabledButton(/Theme|Tema/i, 'guest theme trigger'));
    fireEvent.click(getEnabledButton(/Dark|Întunecat/i, 'guest dark option'));
    await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true));
    expect(authServiceMock.updateThemePreference).not.toHaveBeenCalled();

    fireEvent.mouseDown(getEnabledButton(/Language|Limba/i, 'guest language trigger'));
    fireEvent.click(getEnabledButton(/Romanian|Română/i, 'guest Romanian option'));
    await waitFor(() => expect(document.documentElement.lang).toBe('ro'));
    expect(authServiceMock.updateLanguagePreference).not.toHaveBeenCalled();
  });

  it('covers desktop theme and language preference save success and failure paths', async () => {
    authState.isAuthenticated = true;
    authState.isOrganizer = false;
    authState.isAdmin = false;
    authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

    authServiceMock.updateThemePreference.mockResolvedValueOnce(undefined);
    authServiceMock.updateThemePreference.mockRejectedValueOnce(new Error('theme-fail'));
    authServiceMock.updateLanguagePreference.mockResolvedValueOnce(undefined);
    authServiceMock.updateLanguagePreference.mockRejectedValueOnce(new Error('lang-fail'));

    render(
      <MemoryRouter>
        <ThemeProvider>
          <LanguageProvider>
            <Navbar />
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    fireEvent.mouseDown(getEnabledButton(/Theme|Tema/i, 'enabled theme trigger'));
    fireEvent.click(getEnabledButton(/Light|Luminos/i, 'enabled light button'));
    await waitFor(() => {
      const hasLight = authServiceMock.updateThemePreference.mock.calls.some(
        ([value]) => value === 'light',
      );
      expect(hasLight).toBe(true);
    });

    await waitFor(() => {
      expect(
        screen
          .getAllByRole('button', { name: /Theme|Tema/i })
          .some((button) => !button.hasAttribute('disabled')),
      ).toBe(true);
    });
    fireEvent.mouseDown(
      getEnabledButton(/Theme|Tema/i, 'enabled theme trigger after light save'),
    );
    fireEvent.click(getEnabledButton(/Dark|Întunecat/i, 'enabled dark button'));
    await waitFor(() => {
      const hasDark = authServiceMock.updateThemePreference.mock.calls.some(
        ([value]) => value === 'dark',
      );
      expect(hasDark).toBe(true);
    });
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.mouseDown(getEnabledButton(/Language|Limba/i, 'enabled language trigger'));
    fireEvent.click(getEnabledButton(/Romanian|Română/i, 'enabled Romanian button'));
    await waitFor(() => {
      const hasRomanian = authServiceMock.updateLanguagePreference.mock.calls.some(
        ([value]) => value === 'ro',
      );
      expect(hasRomanian).toBe(true);
    });

    await waitFor(() =>
      expect(
        getEnabledButton(/Language|Limba/i, 'enabled language trigger after Romanian save'),
      ).toBeDefined(),
    );
    fireEvent.mouseDown(
      getEnabledButton(/Language|Limba/i, 'enabled language trigger after Romanian save'),
    );
    fireEvent.click(getEnabledButton(/^English$/i, 'enabled English button'));
    await waitFor(() => {
      const hasEnglish = authServiceMock.updateLanguagePreference.mock.calls.some(
        ([value]) => value === 'en',
      );
      expect(hasEnglish).toBe(true);
    });
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 15000);

  it('covers mobile dropdown option branches explicitly', async () => {
    authState.isAuthenticated = true;
    authState.isOrganizer = true;
    authState.isAdmin = true;
    authState.user = { full_name: 'Alex User', email: 'alex@test.local', role: 'student' };

    render(
      <MemoryRouter>
        <ThemeProvider>
          <LanguageProvider>
            <Navbar />
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    const menuButton = requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'guest mobile menu button',
    );
    fireEvent.click(menuButton);

    const mobilePanel = requireValue(
      Array.from(document.querySelectorAll('div')).find((node) => {
        const className = typeof node.className === 'string' ? node.className : '';
        return className.includes('top-16') && className.includes('md:hidden');
      }),
      'mobile panel',
    );

    within(mobilePanel)
      .getAllByRole('button', { name: /System|Sistem/i })
      .forEach((button) => fireEvent.click(button));
    within(mobilePanel)
      .getAllByRole('button', { name: /Light|Luminos/i })
      .forEach((button) => fireEvent.click(button));
    within(mobilePanel)
      .getAllByRole('button', { name: /Dark|Întunecat/i })
      .forEach((button) => fireEvent.click(button));

    within(mobilePanel)
      .getAllByRole('button', { name: /Romanian|Română/i })
      .forEach((button) => fireEvent.click(button));
    within(mobilePanel)
      .getAllByRole('button', { name: /^English$/i })
      .forEach((button) => fireEvent.click(button));

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
  });
});
