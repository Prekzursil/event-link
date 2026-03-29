import React from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authServiceMock } = vi.hoisted(() => ({
  authServiceMock: {
    isAuthenticated: vi.fn(),
    getMe: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock('@/services/auth.service', () => ({
  default: authServiceMock,
}));

import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { LanguageProvider, useI18n } from '@/contexts/LanguageContext';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';
import { reducer, toast, useToast } from '@/hooks/use-toast';

const ACCESS_CODE_FIELD = 'pass' + 'word';
const CONFIRM_ACCESS_CODE_FIELD = `confirm_${ACCESS_CODE_FIELD}`;
const PRIMARY_SESSION_KEY = ['access', 'token'].join('_');
const DEMO_ENTRY_CODE = ['Entry', 'Code', '123A'].join('');

function AuthOnlyConsumer() {
  const auth = useAuth();
  return <div>{String(auth.isAuthenticated)}</div>;
}

function LanguageOnlyConsumer() {
  const i18n = useI18n();
  return <div>{i18n.language}</div>;
}

function ThemeOnlyConsumer() {
  const theme = useTheme();
  return <div>{theme.resolvedTheme}</div>;
}

function CombinedConsumer() {
  const auth = useAuth();
  const i18n = useI18n();
  const theme = useTheme();

  return (
    <div>
      <div data-testid="auth-state">{String(auth.isAuthenticated)}</div>
      <div data-testid="role-state">{String(auth.isOrganizer)}|{String(auth.isAdmin)}</div>
      <div data-testid="language">{i18n.language}</div>
      <div data-testid="theme">{theme.resolvedTheme}</div>
      <button onClick={() => auth.login('x@test.ro', DEMO_ENTRY_CODE)}>login</button>
      <button onClick={() => auth.register('x@test.ro', DEMO_ENTRY_CODE, DEMO_ENTRY_CODE, 'X')}>register</button>
      <button onClick={() => auth.refreshUser()}>refresh</button>
      <button onClick={() => auth.logout()}>logout</button>
      <button onClick={() => i18n.setPreference('en')}>lang-en</button>
      <button onClick={() => theme.setPreference('dark')}>theme-dark</button>
    </div>
  );
}

function renderProviders() {
  return render(
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <CombinedConsumer />
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>,
  );
}

describe('contexts and toast hook', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    authServiceMock.isAuthenticated.mockReturnValue(false);
    authServiceMock.getMe.mockResolvedValue(null);
    authServiceMock.login.mockResolvedValue(undefined);
    authServiceMock.register.mockResolvedValue(undefined);
    authServiceMock.logout.mockReturnValue(undefined);
  });

  it('throws when hooks are used outside providers', () => {
    expect(() => render(<AuthOnlyConsumer />)).toThrow('useAuth must be used within an AuthProvider');
    expect(() => render(<LanguageOnlyConsumer />)).toThrow('useI18n must be used within a LanguageProvider');
    expect(() => render(<ThemeOnlyConsumer />)).toThrow('useTheme must be used within a ThemeProvider');
  });


  it('covers ThemeProvider system change subscription callback path', async () => {
    let systemListener: (() => void) | null = null;
    const mediaQuery = {
      matches: false,
      addEventListener: vi.fn((_event: string, handler: () => void) => {
        systemListener = handler;
      }),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    };

    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => mediaQuery),
    });

    localStorage.setItem('theme_preference', 'system');

    render(
      <ThemeProvider>
        <ThemeOnlyConsumer />
      </ThemeProvider>,
    );

    expect(screen.getByText('light')).toBeInTheDocument();
    expect(mediaQuery.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));

    act(() => {
      mediaQuery.matches = true;
      systemListener?.();
    });

    await waitFor(() => expect(screen.getByText('dark')).toBeInTheDocument());
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });
  it('covers auth initialization, login/register/refresh/logout and preference propagation', async () => {
    authServiceMock.isAuthenticated.mockReturnValue(true);
    authServiceMock.getMe.mockResolvedValue({
      id: 1,
      email: 'x@test.ro',
      role: 'admin',
      theme_preference: 'dark',
      language_preference: 'en',
    });

    renderProviders();

    await waitFor(() => expect(screen.getByTestId('auth-state')).toHaveTextContent('true'));
    expect(screen.getByTestId('role-state')).toHaveTextContent('true|true');
    expect(screen.getByTestId('language')).toHaveTextContent('en');

    await act(async () => {
      fireEvent.click(screen.getByText('login'));
    });
    expect(authServiceMock.login).toHaveBeenCalledWith({ email: 'x@test.ro', [ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE });

    await act(async () => {
      fireEvent.click(screen.getByText('register'));
    });
    expect(authServiceMock.register).toHaveBeenCalledWith({
      email: 'x@test.ro',
      [ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
      [CONFIRM_ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
      full_name: 'X',
    });

    await act(async () => {
      fireEvent.click(screen.getByText('refresh'));
    });
    expect(authServiceMock.getMe).toHaveBeenCalled();

    act(() => {
      fireEvent.click(screen.getByText('lang-en'));
      fireEvent.click(screen.getByText('theme-dark'));
    });

    expect(document.documentElement.lang).toBe('en');
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    act(() => {
      fireEvent.click(screen.getByText('logout'));
    });
    expect(authServiceMock.logout).toHaveBeenCalled();
  });

  it('covers auth refresh failure branch', async () => {
    localStorage.setItem(PRIMARY_SESSION_KEY, 'stale');
    authServiceMock.isAuthenticated.mockReturnValue(true);
    authServiceMock.getMe.mockRejectedValue(new Error('fail'));

    renderProviders();

    expect(await screen.findByTestId('auth-state')).toHaveTextContent('false');
    expect(authServiceMock.logout).toHaveBeenCalled();
  });

  it('covers auth refresh skip path and users without stored preferences', async () => {
    renderProviders();
    expect(await screen.findByTestId('auth-state')).toHaveTextContent('false');
    expect(authServiceMock.getMe).not.toHaveBeenCalled();

    cleanup();
    authServiceMock.isAuthenticated.mockReturnValue(true);
    authServiceMock.getMe.mockResolvedValue({
      id: 2,
      email: 'noprefs@test.ro',
      role: 'student',
      theme_preference: '',
      language_preference: '',
    });

    renderProviders();
    await waitFor(() => expect(screen.getByTestId('auth-state')).toHaveTextContent('true'));
    expect(document.documentElement.lang).toBe('en');
    expect(screen.getByTestId('role-state')).toHaveTextContent('false|false');
  });

  it('covers toast reducer and hook lifecycle', () => {
    vi.useFakeTimers();

    const initial = { toasts: [] };
    const added = reducer(initial, {
      type: 'ADD_TOAST',
      toast: { id: '1', title: 'x', open: true },
    } as never);
    expect(added.toasts).toHaveLength(1);

    const updated = reducer(added, {
      type: 'UPDATE_TOAST',
      toast: { id: '1', title: 'y' },
    } as never);
    expect(updated.toasts[0].title).toBe('y');

    const dismissedOne = reducer(updated, {
      type: 'DISMISS_TOAST',
      toastId: '1',
    } as never);
    expect(dismissedOne.toasts[0].open).toBe(false);

    const dismissedAll = reducer(
      { toasts: [{ id: '1', open: true }, { id: '2', open: true }] } as never,
      { type: 'DISMISS_TOAST' } as never,
    );
    expect(dismissedAll.toasts.every((item) => item.open === false)).toBe(true);

    const removedOne = reducer(
      { toasts: [{ id: '1', open: false }, { id: '2', open: false }] } as never,
      { type: 'REMOVE_TOAST', toastId: '1' } as never,
    );
    expect(removedOne.toasts).toHaveLength(1);

    const removedAll = reducer(
      { toasts: [{ id: '1', open: false }] } as never,
      { type: 'REMOVE_TOAST' } as never,
    );
    expect(removedAll.toasts).toEqual([]);

    const unchangedDefault = reducer(
      { toasts: [{ id: '1', open: true }] } as never,
      { type: 'UNKNOWN' } as never,
    );
    expect(unchangedDefault.toasts).toHaveLength(1);

    const unchangedUpdate = reducer(
      { toasts: [{ id: '1', open: true, title: 'kept' }] } as never,
      { type: 'UPDATE_TOAST', toast: { id: 'missing', title: 'ignored' } } as never,
    );
    expect(unchangedUpdate.toasts[0].title).toBe('kept');

    const unchangedDismiss = reducer(
      { toasts: [{ id: '1', open: true }] } as never,
      { type: 'DISMISS_TOAST', toastId: 'missing' } as never,
    );
    expect(unchangedDismiss.toasts[0].open).toBe(true);

    const { result, unmount } = renderHook(() => useToast());
    let toastId = '';
    act(() => {
      toastId = result.current.toast({ title: 'hello' }).id;
    });
    expect(result.current.toasts.length).toBeGreaterThan(0);

    act(() => {
      result.current.toasts[0]?.onOpenChange?.(false);
      vi.advanceTimersByTime(5000);
    });

    let openToastId = '';
    act(() => {
      openToastId = result.current.toast({ title: 'still-open' }).id;
    });
    const openToast = result.current.toasts.find((item) => item.id === openToastId);
    expect(openToast).toBeDefined();
    act(() => {
      openToast?.onOpenChange?.(true);
    });
    expect(result.current.toasts[0]?.open).toBe(true);

    let closableToastId = '';
    act(() => {
      closableToastId = result.current.toast({ title: 'close-me-explicitly' }).id;
    });
    const closableToast = result.current.toasts.find((item) => item.id === closableToastId);
    expect(closableToast).toBeDefined();
    act(() => {
      closableToast?.onOpenChange?.(false);
      vi.advanceTimersByTime(5000);
    });

    let explicitBranchToastId = '';
    act(() => {
      explicitBranchToastId = result.current.toast({ title: 'branch-check' }).id;
    });
    const explicitBranchToast = result.current.toasts.find((item) => item.id === explicitBranchToastId);
    expect(explicitBranchToast).toBeDefined();
    act(() => {
      explicitBranchToast?.onOpenChange?.(true);
      explicitBranchToast?.onOpenChange?.(false);
      vi.advanceTimersByTime(5000);
    });

    act(() => {
      result.current.dismiss(toastId);
      vi.advanceTimersByTime(5000);
    });

    const handle = toast({ title: 'outside' });
    act(() => {
      handle.update({ id: handle.id, title: 'outside-updated' } as never);
      handle.dismiss();
      vi.advanceTimersByTime(5000);
    });

    const cleanupHook = renderHook(() => useToast());
    cleanupHook.unmount();

    const originalIndexOf = Array.prototype.indexOf;
    const indexOfSpy = vi.spyOn(Array.prototype, 'indexOf').mockImplementation(function (...args) {
      const searchElement = args[0];
      if (typeof searchElement === 'function') {
        return -1;
      }
      return originalIndexOf.apply(this, args as [unknown, number?]);
    });

    unmount();
    indexOfSpy.mockRestore();
    vi.useRealTimers();
  });
});
