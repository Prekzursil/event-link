import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';
import { ThemeProvider } from '@/contexts/ThemeContext';

const { authState, toastSpy, toastState, authServiceMock } = vi.hoisted(() => ({
  authState: {
    isAuthenticated: false,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: null as { full_name?: string | null; email?: string; role?: string } | null,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  toastSpy: vi.fn(),
  toastState: {
    toasts: [] as Array<{
      id: string;
      open: boolean;
      title?: string;
      description?: string;
      variant?: 'default' | 'destructive' | 'success';
    }>,
  },
  authServiceMock: {
    updateThemePreference: vi.fn(),
    updateLanguagePreference: vi.fn(),
  },
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy, toasts: toastState.toasts }),
}));

vi.mock('@/services/auth.service', () => ({
  default: authServiceMock,
}));
vi.mock('@/components/ui/dropdown-menu', () =>
  import('./mock-component-modules').then((module) => module.createDropdownMenuMockModule()),
);

import { Footer, Layout, Navbar } from '@/components/layout';
import {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from '@/components/ui/toast';
import { Toaster } from '@/components/ui/toaster';

function requireValue<T>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`Expected ${label}`);
  }
  return value;
}

describe('layout and ui smoke', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.setItem('language_preference', 'en');
    authState.isAuthenticated = false;
    authState.isOrganizer = false;
    authState.isAdmin = false;
    authState.user = null;
    toastState.toasts = [];
    authServiceMock.updateLanguagePreference.mockResolvedValue(undefined);
    authServiceMock.updateThemePreference.mockResolvedValue(undefined);
    authState.refreshUser.mockResolvedValue(undefined);

    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders navbar for guest and opens mobile menu', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <LanguageProvider>
            <Navbar />
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/EventLink/i)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /Register/i }).length).toBeGreaterThan(0);

    const menuButton = requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'guest mobile menu button',
    );
    fireEvent.click(menuButton);

    expect(screen.getAllByRole('link', { name: /Log in/i }).length).toBeGreaterThan(0);
  }, 15000);

  it('renders authenticated navbar and triggers logout from mobile menu', () => {
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

    expect(screen.getAllByRole('link', { name: /Dashboard/i }).length).toBeGreaterThan(0);

    const menuButton = requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'authenticated mobile menu button',
    );
    fireEvent.click(menuButton);

    fireEvent.click(screen.getAllByRole('button', { name: /Log out/i })[0]);
    expect(authState.logout).toHaveBeenCalled();
  });

  it('covers desktop theme/language preference save success and failure paths', async () => {
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

    fireEvent.mouseDown(screen.getAllByRole('button', { name: /Theme|Tema/i })[0]);
    screen.getAllByRole('button', { name: /Light|Luminos/i }).forEach((button) => fireEvent.click(button));
    await waitFor(() => {
      const hasLight = authServiceMock.updateThemePreference.mock.calls.some(([value]) => value === 'light');
      expect(hasLight).toBe(true);
    });

    fireEvent.mouseDown(screen.getAllByRole('button', { name: /Theme|Tema/i })[0]);
    screen.getAllByRole('button', { name: /Dark|Întunecat/i }).forEach((button) => fireEvent.click(button));
    await waitFor(() => {
      const hasDark = authServiceMock.updateThemePreference.mock.calls.some(([value]) => value === 'dark');
      expect(hasDark).toBe(true);
    });
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.mouseDown(screen.getAllByRole('button', { name: /Language|Limba/i })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: /Romanian|Română/i })[0]);
    await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalledWith('ro'));

    fireEvent.mouseDown(screen.getAllByRole('button', { name: /Language|Limba/i })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: /^English$/i })[0]);
    await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalledWith('en'));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  }, 15000);


  it('covers navbar system selectors and mobile link close handlers', async () => {
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
      screen.getAllByRole('link', { name: /Dashboard/i }).find((link) => link.className.includes('rounded-md')),
      'dashboard link',
    );
    fireEvent.click(dashboardLink);

    const newEventLinks = screen
      .getAllByRole('link', { name: /New event|Event nou/i });
    expect(newEventLinks.length).toBeGreaterThan(0);
    fireEvent.click(newEventLinks[newEventLinks.length - 1]);

    const logoutButtons = screen.getAllByRole('button', { name: /Log out/i });
    fireEvent.click(logoutButtons[logoutButtons.length - 1]);
    expect(authState.logout).toHaveBeenCalled();

    cleanup();
    authState.isAuthenticated = false;
    authState.isOrganizer = false;
    authState.isAdmin = false;
    authState.user = null;

    render(
      <MemoryRouter>
        <ThemeProvider>
          <LanguageProvider>
            <Navbar />
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    const guestMenuButton = requireValue(
      screen.getAllByRole('button').find((button) => button.className.includes('md:hidden')),
      'guest mobile menu button',
    );
    fireEvent.click(guestMenuButton);

    const loginLink = requireValue(
      screen.getAllByRole('link', { name: /Log in/i }).find((link) => link.className.includes('w-full')),
      'login link',
    );
    const registerLink = requireValue(
      screen.getAllByRole('link', { name: /Register/i }).find((link) => link.className.includes('w-full')),
      'register link',
    );
    fireEvent.click(loginLink);
    fireEvent.click(registerLink);
  }, 20000);

  it('covers initials fallback branches in avatar', () => {
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
  it('renders footer and layout index exports', () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Footer />
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/All rights reserved/i)).toBeInTheDocument();

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <LanguageProvider>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<div>Outlet Content</div>} />
              </Route>
            </Routes>
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Outlet Content')).toBeInTheDocument();
  });

  it('renders toast primitives and toaster list mapping', () => {
    toastState.toasts = [
      {
        id: '1',
        open: true,
        title: 'Toast title',
        description: 'Toast description',
        variant: 'default',
      },
    ];

    render(
      <ToastProvider>
        <Toast open>
          <div>
            <ToastTitle>Primitive title</ToastTitle>
            <ToastDescription>Primitive description</ToastDescription>
          </div>
          <ToastAction altText="action">Action</ToastAction>
          <ToastClose />
        </Toast>
        <ToastViewport />
      </ToastProvider>,
    );

    expect(screen.getByText('Primitive title')).toBeInTheDocument();
    expect(screen.getByText('Primitive description')).toBeInTheDocument();

    render(<Toaster />);
    expect(screen.getByText('Toast title')).toBeInTheDocument();
  });
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
});

