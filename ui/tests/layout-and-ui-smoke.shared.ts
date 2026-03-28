import { cleanup, screen } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

function createAuthState() {
  return {
    isAuthenticated: false,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: null as { full_name?: string | null; email?: string; role?: string } | null,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };
}

function createToastState() {
  return {
    toasts: [] as Array<{
      id: string;
      open: boolean;
      title?: string;
      description?: string;
      variant?: 'default' | 'destructive' | 'success';
    }>,
  };
}

function createAuthServiceMock() {
  return {
    updateThemePreference: vi.fn(),
    updateLanguagePreference: vi.fn(),
  };
}

const layoutUiFixtures = vi.hoisted(() => ({
  authState: createAuthState(),
  toastSpy: vi.fn(),
  toastState: createToastState(),
  authServiceMock: createAuthServiceMock(),
}));

const { authState, toastSpy, toastState, authServiceMock } = layoutUiFixtures;

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

export const { LanguageProvider } = await import('@/contexts/LanguageContext');
export const { ThemeProvider } = await import('@/contexts/ThemeContext');
export const { Footer, Layout, Navbar } = await import('@/components/layout');
export const {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} = await import('@/components/ui/toast');
export const { Toaster } = await import('@/components/ui/toaster');

export function getLayoutUiFixtures() {
  return layoutUiFixtures;
}

export function requireValue<T>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`Expected ${label}`);
  }
  return value;
}

export function getEnabledButton(
  name: Parameters<typeof screen.getAllByRole>[1]['name'],
  label: string,
) {
  return requireValue(
    screen.getAllByRole('button', { name }).find((button) => !button.hasAttribute('disabled')),
    label,
  );
}

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
