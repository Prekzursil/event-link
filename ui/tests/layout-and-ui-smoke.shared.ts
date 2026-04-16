import { cleanup, screen } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

/**
 * Test helper: create auth state.
 */
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

/**
 * Test helper: create toast state.
 */
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

/**
 * Test helper: create auth service mock.
 */
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

/**
 * Test helper: get layout ui fixtures.
 */
export function getLayoutUiFixtures() {
  return layoutUiFixtures;
}

/**
 * Returns the value value or fails loudly when absent.
 */
export function requireValue<T>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`Expected ${label}`);
  }
  return value;
}

/**
 * Test helper: get enabled button.
 */
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
  authServiceMock.updateLanguagePreference.mockResolvedValue();
  authServiceMock.updateThemePreference.mockResolvedValue();
  authState.refreshUser.mockResolvedValue();

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
